from odoo import http, fields
from odoo.http import request
import json

class SaleOrderAPIController(http.Controller):

    @http.route('/api/create_order', type='json', auth='none', methods=['POST'], csrf=False, cors='*')
    def create_order(self, **kwargs):
        try:
            token = request.httprequest.headers.get('X-API-Key')
            configured_key = request.env['ir.config_parameter'].sudo().get_param('api.product_access_key')
            if token != configured_key:
                return {'error': 'Unauthorized'}, 401

            customer_id = kwargs.get('customer_id')
            payment_status = kwargs.get('payment_status')
            order_lines = kwargs.get('order_lines', [])

            if not customer_id:
                return {'error': 'Missing customer_id'}, 400
            if not isinstance(order_lines, list) or not order_lines:
                return {'error': 'Invalid or missing order_lines'}, 400

            system_user = request.env.ref('base.user_admin')

            sale_order = request.env['sale.order'].with_user(system_user).sudo().create({
                'partner_id': customer_id
            })

            for line in order_lines:
                product_id = line.get('product_id')
                quantity = line.get('quantity', 1)

                product = request.env['product.product'].sudo().browse(product_id)
                if not product.exists():
                    return {'error': f'Product ID {product_id} not found'}, 400

                request.env['sale.order.line'].with_user(system_user).sudo().create({
                    'order_id': sale_order.id,
                    'product_id': product.id,
                    'product_uom_qty': quantity,
                    'price_unit': product.lst_price,
                    'name': product.name,
                })

            sale_order.with_user(system_user).action_confirm()

            pickings = sale_order.picking_ids.filtered(lambda p: p.state not in ['done', 'cancel'])

            for picking in pickings:
                picking.action_confirm()
                picking.action_assign()

                for move in picking.move_ids_without_package:
                    move.move_line_ids.unlink()

                    request.env['stock.move.line'].sudo().create({
                        'move_id': move.id,
                        'picking_id': picking.id,
                        'product_id': move.product_id.id,
                        'product_uom_id': move.product_uom.id,
                        'qty_done': move.product_uom_qty,
                        'location_id': move.location_id.id,
                        'location_dest_id': move.location_dest_id.id,
                    })

                picking.button_validate()

            invoice = sale_order._create_invoices()

            if payment_status == 'paid':
                journal = request.env['account.journal'].sudo().search([('type', '=', 'bank')], limit=1)
                if not journal:
                    return {'error': 'No bank journal found'}, 500

                payment_wizard = request.env['account.payment.register'].sudo().with_context(
                    active_model='account.move',
                    active_ids=invoice.ids
                ).create({
                    'payment_date': fields.Date.today(),
                    'journal_id': journal.id,
                    'amount': invoice.amount_total,
                })
                payment_wizard.action_create_payments()

            if sale_order.partner_id.email:
                template = request.env.ref('account.email_template_edi_invoice')
                invoice.message_post_with_template(template.id)

            return {
                "message": "Sale Order and Invoice created successfully",
                "sale_order_id": sale_order.id,
                "invoice_id": invoice.id,
                "status": payment_status
            }

        except Exception as e:
            return {'error': str(e)}, 500
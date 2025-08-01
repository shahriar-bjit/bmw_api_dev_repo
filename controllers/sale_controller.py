from odoo import http, fields
from odoo.http import request

class SaleOrderAPIController(http.Controller):
    @http.route('/api/create_order', type='json', auth='none', methods=['POST'], csrf=False, cors='*')
    def create_order(self, **kwargs):
        try:
            token = request.httprequest.headers.get('X-API-Key')
            configured_key = request.env['ir.config_parameter'].sudo().get_param('api.product_access_key')
            if token != configured_key:
                return {'error': 'Unauthorized'}, 401

            products = kwargs.get('products', [])
            payment_status = kwargs.get('payment_status', '').lower()
            delivery_address = kwargs.get('delivery_address')

            if not products or not isinstance(products, list):
                return {'error': 'Invalid or missing products list'}, 400

            system_user = request.env.ref('base.user_admin')

            customer = request.env['res.partner'].sudo().search([('customer_rank', '>', 0)], limit=1)
            if not customer:
                return {'error': 'No customer found in the system'}, 400

            if delivery_address:
                delivery_partner = request.env['res.partner'].sudo().create({
                    'name': customer.name + ' (Delivery)',
                    'street': delivery_address,
                    'type': 'delivery',
                    'parent_id': customer.id,
                })
            else:
                delivery_partner = customer

            sale_order = request.env['sale.order'].with_user(system_user).sudo().create({
                'partner_id': customer.id,
                'partner_shipping_id': delivery_partner.id,
            })

            for line in products:
                product_code = line.get('product_code')
                quantity = line.get('quantity', 1)

                if not product_code:
                    return {'error': 'Missing product_code in line item'}, 400

                product = request.env['product.product'].sudo().search([('default_code', '=', product_code)], limit=1)
                if not product:
                    return {'error': f'Product with code {product_code} not found'}, 400

                request.env['sale.order.line'].with_user(system_user).sudo().create({
                    'order_id': sale_order.id,
                    'product_id': product.id,
                    'product_uom_qty': quantity,
                    'price_unit': product.lst_price,
                    'name': product.name,
                })

            invoice = None

            if payment_status == 'paid':
                if sale_order.state == 'draft':
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
                invoice = invoice and invoice.exists() and invoice[0] or None

                if invoice:
                    invoice.action_post()

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

            return {
                "message": "Sale Order created successfully",
                "sale_order": sale_order.name,
                "invoice": invoice.name if invoice else None,
                "status": payment_status.capitalize() or 'Unpaid'
            }

        except Exception as e:
            return {'error': str(e)}, 500

    @http.route('/api/track_order', type='json', auth='none', methods=['POST'], csrf=False, cors='*')
    def track_order(self, **kwargs):
        try:
            token = request.httprequest.headers.get('X-API-Key')
            configured_key = request.env['ir.config_parameter'].sudo().get_param('api.product_access_key')
            if token != configured_key:
                return {'error': 'Unauthorized'}, 401

            sale_order_id = kwargs.get('sale_order_id')
            if not sale_order_id:
                return {'status': 'Failure', 'reason': 'Missing sale_order_id'}, 400

            sale_order = request.env['sale.order'].sudo().browse(int(sale_order_id))
            if not sale_order:
                return {'status': 'Failure', 'reason': 'Sale Order not found'}, 404

            order_lines = []
            for line in sale_order.order_line:
                order_lines.append({
                    'product': line.product_id.name,
                    'quantity': line.product_uom_qty,
                    'unit_price': line.price_unit,
                    'subtotal': line.price_subtotal,
                })

            payment_state = sale_order.invoice_status

            if payment_state == 'invoiced':
                payment_status = 'Paid' if all(inv.payment_state == 'paid' for inv in sale_order.invoice_ids) else 'Unpaid'
            else:
                payment_status = 'Not Invoiced'

            if sale_order.picking_ids:
                delivered = all(p.state == 'done' for p in sale_order.picking_ids)
                delivery_status = 'Shipped' if delivered else 'Pending'
            else:
                delivery_status = 'No Delivery'

            return {
                'status': 'Success',
                'order_id': sale_order.id,
                'customer': sale_order.partner_id.name,
                'order_lines': order_lines,
                'total_amount': sale_order.amount_total,
                'payment_status': payment_status,
                'delivery_status': delivery_status
            }
        except Exception as e:
            return {'error': str(e)}, 500
from odoo import http
from odoo.http import request
import json

class ProductAPIController(http.Controller):

    @http.route('/api/products', type='json', auth='none', methods=['GET', 'POST'], csrf=False, cors='*')
    def get_products(self, *args, **kwargs):
        try:
            configured_key = request.env['ir.config_parameter'].sudo().get_param('api.product_access_key')

            token = request.httprequest.headers.get('X-API-Key')
            if token != configured_key:
                return {'error': 'Unauthorized'}, 401

            offset = int(kwargs.get('offset', 0))
            limit = int(kwargs.get('limit', 50))

            products = request.env['product.product'].sudo().search([], offset=offset, limit=limit)

            result = []
            for product in products:
                result.append({
                    'id': product.id,
                    'name': product.name,
                    'image_url': f"http://127.0.0.1:8018/web/image/product.product/{product.id}/image_1920",
                    'on_hand_qty': product.qty_available,
                    'unit_price': product.lst_price,
                })

            return ({
                    'products': result,
                    'offset': offset,
                    'limit': limit,
                    'count': len(result)
            }),

        except Exception as e:
            return {'error': str(e)}, 500
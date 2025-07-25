from odoo import http
from odoo.http import request
import base64


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

            base_url = self._get_base_url(request)

            result = []
            for product in products:
                image_url = None
                if product.image_1920:
                    image_url = f"{base_url}/api/product/image/{product.id}"

                result.append({
                    'id': product.id,
                    'name': product.name,
                    'image_url': image_url,
                    'on_hand_qty': product.qty_available,
                    'unit_price': product.lst_price,
                })

            return {
                'products': result,
                'offset': offset,
                'limit': limit,
                'count': len(result)
            }

        except Exception as e:
            return {'error': str(e)}, 500

    def _get_base_url(self, request):
        if request.httprequest.headers.get('X-Forwarded-Host'):
            protocol = 'https' if request.httprequest.headers.get('X-Forwarded-Proto') == 'https' else 'http'
            host = request.httprequest.headers.get('X-Forwarded-Host')
            return f"{protocol}://{host}"

        return f"{request.httprequest.scheme}://{request.httprequest.host}"

    @http.route('/api/product/image/<int:product_id>', type='http', auth='public', methods=['GET'], csrf=False, cors='*')
    def get_product_image(self, product_id, **kwargs):
        try:
            configured_key = request.env['ir.config_parameter'].sudo().get_param('api.product_access_key')
            token = request.httprequest.args.get('api_key') or request.httprequest.headers.get('X-API-Key')

            if token != configured_key:
                return request.not_found()

            product = request.env['product.product'].sudo().browse(product_id)
            if not product.exists() or not product.image_1920:
                return request.not_found()

            image_data = base64.b64decode(product.image_1920)
            headers = [
                ('Content-Type', 'image/jpeg'),
                ('Content-Length', len(image_data)),
                ('Cache-Control', 'public, max-age=3600'),
                ('Access-Control-Allow-Origin', '*'),
            ]

            return request.make_response(image_data, headers)

        except Exception as e:
            return request.not_found()
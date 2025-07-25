from odoo import http
from odoo.http import request
import jwt
import datetime


class UserSignupAPI(http.Controller):

    @http.route('/api/signup', type='json', auth='none', methods=['POST'], csrf=False)
    def signup_user(self, **kwargs):
        try:
            name = kwargs.get('name')
            email = kwargs.get('email')
            phone = kwargs.get('phone')
            password = kwargs.get('password')

            if not name or not email or not password:
                return {'error': 'Missing required fields: name, email, password'}, 400

            existing_users = request.env['res.users'].sudo().search([('login', '=', email)])
            if existing_users:
                return {'error': 'User with this email already exists'}, 409
            try:
                superuser = request.env['res.users'].sudo().browse(2)
                if not superuser.exists():
                    superuser = request.env['res.users'].sudo().browse(1)

                if not superuser.exists():
                    return {'error': 'No valid system user found'}, 500

                user_env = request.env(user=superuser)

                partner_vals = {
                    'name': name,
                    'email': email,
                    'is_company': False,
                    'customer_rank': 1,
                }
                if phone:
                    partner_vals['phone'] = phone

                partner = user_env['res.partner'].sudo().create(partner_vals)

                company = user_env['res.company'].sudo().search([], limit=1)
                if not company:
                    return {'error': 'No company found'}, 500

                portal_group = user_env.ref('base.group_portal')

                user_vals = {
                    'name': name,
                    'login': email,
                    'email': email,
                    'password': password,
                    'partner_id': partner.id,
                    'company_id': company.id,
                    'company_ids': [(6, 0, [company.id])],
                    'groups_id': [(6, 0, [portal_group.id])],
                    'active': True,
                    'share': True,
                }

                if phone:
                    user_vals['phone'] = phone

                new_user = user_env['res.users'].sudo().create(user_vals)

                if not new_user or len(new_user) == 0:
                    # Fallback: search for the user in case it was created despite the error
                    found_user = user_env['res.users'].sudo().search([('login', '=', email)], limit=1)
                    if found_user:
                        print(f"Found user via search: {found_user.id}")
                        new_user = found_user
                    else:
                        return {'error': 'User creation failed completely'}, 500

                user_id = new_user.id

                try:
                    secret_key = request.env['ir.config_parameter'].sudo().get_param(
                        'jwt.secret_key') or 'odoo_default_secret'
                    expiration = datetime.datetime.utcnow() + datetime.timedelta(hours=24)
                    payload = {
                        'user_id': user_id,
                        'email': email,
                        'exp': expiration
                    }
                    token = jwt.encode(payload, secret_key, algorithm='HS256')
                    print("✅ JWT generated")
                except Exception as jwt_err:
                    print(f"JWT failed: {jwt_err}")
                    token = None

                return {
                    'success': True,
                    'message': 'Account created successfully',
                    'user_id': user_id,
                    'token': token
                }

            except Exception as creation_err:
                print(f"❌ Creation error: {creation_err}")
                import traceback
                print(f"Traceback: {traceback.format_exc()}")
                return {'error': f'User creation failed: {str(creation_err)}'}, 500

        except Exception as e:
            print(f"❌ Top-level error: {e}")
            import traceback
            print(f"Full traceback: {traceback.format_exc()}")
            return {'error': str(e)}, 500
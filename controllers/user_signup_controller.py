from odoo import http
from odoo.http import request
import secrets
import string

class UserSignupAPI(http.Controller):
    def _get_base_url(self, request):
        if request.httprequest.headers.get('X-Forwarded-Host'):
            protocol = 'https' if request.httprequest.headers.get('X-Forwarded-Proto') == 'https' else 'http'
            host = request.httprequest.headers.get('X-Forwarded-Host')

            return f"{protocol}://{host}"

        return f"{request.httprequest.scheme}://{request.httprequest.host}"

    def _send_login_email(self, admin_env, user, password, user_name):
        try:
            base_url = self._get_base_url(request)

            api_reset_link = f"{base_url}/api/reset_password"

            template = admin_env.ref('product_rest_api.customer_signup_account_created_template')
            ctx = {
                'password': password,
                'reset_link': api_reset_link,
            }
            template.with_context(ctx).sudo().send_mail(user.id, force_send=True)

            try:
                user.action_reset_password()
                print("Password reset email sent via Odoo's built-in system")
            except Exception as reset_err:
                print(f"Password reset email failed: {reset_err}")

            return True

        except Exception as e:
            return False

    @http.route('/api/otp/send', type='json', auth='none', methods=['POST'], csrf=False, cors='*')
    def send_otp(self, **kwargs):
        email = kwargs.get('email')

        if not email:
            return {'error': 'Email is required'}, 400

        existing_user = request.env['res.users'].sudo().search([('login', '=', email)], limit=1)
        if existing_user:
            return {'error': 'Email is already registered'}, 409

        otp_record = request.env['customer.otp'].sudo().generate_otp(email)
        if not otp_record:
            return {'error': 'Failed to generate OTP'}, 500

        try:
            email_values = {
                'email_from': 'noreply@yourcompany.com',
                'email_to': email,
                'subject': 'Your OTP Code',
                'body_html': f'<p>Your OTP code is: <strong>{otp_record.otp}</strong>. It is valid for 5 minutes.</p>'
            }
            mail = request.env['mail.mail'].sudo().create(email_values)
            mail.sudo().send()
        except Exception as e:
            print(f"Error details: {str(e)}")
            return {'error': f'Failed to send OTP email: {str(e)}'}, 500

        return {'success': True, 'message': f'OTP sent to {email}'}

    @http.route('/api/signup', type='json', auth='none', methods=['POST'], csrf=False, cors='*')
    def signup_user(self, **kwargs):
        new_user = None
        try:
            name = kwargs.get('name')
            email = kwargs.get('email')
            otp = kwargs.get('otp')

            if not name or not email or not otp:
                return {'error': 'Missing required fields: name, email, otp'}, 400

            if '@' not in email:
                return {'error': 'Invalid email format'}, 400

            otp_record = request.env['customer.otp'].sudo().search([('email', '=', email)], limit=1)
            if not otp_record or otp_record.otp != otp:
                return {'error': 'Invalid or expired OTP'}, 401

            characters = string.ascii_letters + string.digits + "!@#$%&*"
            generated_password = ''.join(secrets.choice(characters) for i in range(12))

            try:
                admin_user = request.env.ref('base.user_admin')
                if not admin_user or not admin_user.exists():
                    admin_user = request.env['res.users'].sudo().search([('id', '=', 2)], limit=1)
                if not admin_user or not admin_user.exists():
                    admin_user = request.env['res.users'].sudo().search([('id', '=', 1)], limit=1)
                if not admin_user or not admin_user.exists():
                    return {'error': 'No admin user found'}, 500

            except Exception as admin_err:
                return {'error': 'Admin user configuration error'}, 500

            admin_env = request.env(user=admin_user)

            existing_user = admin_env['res.users'].sudo().search([('login', '=', email)], limit=1)
            if existing_user:
                return {
                    'error': 'User with this email already exists',
                    'existing_user_id': existing_user.id
                }, 409

            company = admin_env['res.company'].sudo().browse(1)
            if not company:
                return {'error': 'No company found'}, 500

            try:
                portal_group = admin_env.ref('base.group_portal')
                if not portal_group:
                    return {'error': 'Portal group not found'}, 500
            except Exception as group_err:
                print(f"Portal group error: {group_err}")

            try:
                user_vals = {
                    'name': name,
                    'login': email,
                    'email': email,
                    'password': generated_password,
                    'company_id': company.id,
                    'company_ids': [(6, 0, [company.id])],
                    'groups_id': [(6, 0, portal_group.ids)],
                    'active': True,
                    'share': True,
                }

                new_user = admin_env['res.users'].sudo().create(user_vals)

                partner = new_user.partner_id
                if not partner:
                    raise Exception('Auto-created partner not found')

            except Exception as user_err:
                return {'error': f'User creation failed: {str(user_err)}'}, 500

            try:
                partner_updates = {
                    'is_company': False,
                    'customer_rank': 1,
                }
                partner.sudo().write(partner_updates)
                otp_record.sudo().unlink()

            except Exception as partner_err:
                return {'error': f'Partner update failed: {str(partner_err)}'}, 500

            try:
                self._send_login_email(admin_env, new_user, generated_password, name)
                email_sent = True
            except Exception as email_err:
                email_sent = False

            return {
                'success': True,
                'message': f'Account created successfully for {name}',
                'customer_id': partner.id,
                'user_id': new_user.id,
                'login_email': email,
                'generated_password': generated_password,
                'email_sent': email_sent,
                'user_share': new_user.share,
                'user_groups': new_user.groups_id.mapped('name')
            }

        except Exception as e:
            return {'error': f'Account creation failed: {str(e)}'}, 500

    @http.route('/api/reset_password', type='json', auth='none', methods=['POST'], csrf=False, cors='*')
    def reset_password(self, **kwargs):
        try:
            email = kwargs.get('email')
            old_password = kwargs.get('old_password')
            new_password = kwargs.get('new_password')

            if not email or not old_password or not new_password:
                return {'error': 'Missing required fields: email, old_password, new_password'}, 400

            if len(new_password) < 8:
                return {'error': 'New password must be at least 8 characters long'}, 400

            try:
                admin_user = request.env.ref('base.user_admin')
                if not admin_user or not admin_user.exists():
                    admin_user = request.env['res.users'].sudo().search([('id', '=', 2)], limit=1)
                if not admin_user or not admin_user.exists():
                    admin_user = request.env['res.users'].sudo().search([('id', '=', 1)], limit=1)

                if not admin_user or not admin_user.exists():
                    return {'error': 'No admin user found'}, 500

            except Exception as admin_err:
                return {'error': 'Admin user configuration error'}, 500

            admin_env = request.env(user=admin_user)

            user = admin_env['res.users'].sudo().search([('login', '=', email)], limit=1)
            if not user:
                return {'error': 'User not found'}, 404

            try:
                user_env = request.env(user=user)
                credential = {
                    'type': 'password',
                    'password': old_password
                }
                user_env.user._check_credentials(credential, user_env)

            except Exception:
                return {'error': 'Invalid current password'}, 401

            user.sudo().write({'password': new_password})

            return {
                'success': True,
                'message': 'Password changed successfully! You can now login with your new password.',
                'user_id': user.id,
                'login_email': user.email,
                'login_url': f"{self._get_base_url(request)}/web/login"
            }

        except Exception as e:
            return {'error': f'Password change failed: {str(e)}'}, 500

    @http.route('/api/shipping_address', type='json', auth='none', methods=['POST'], csrf=False, cors='*')
    def add_update_shipping_address(self, **kwargs):
        try:
            token = request.httprequest.headers.get('X-API-Key')
            configured_key = request.env['ir.config_parameter'].sudo().get_param('api.product_access_key')
            if token != configured_key:
                return {'error': 'Unauthorized'}, 401

            customer_id = kwargs.get('customer_id')
            shipping_address = kwargs.get('shipping_address')

            if not customer_id or not shipping_address:
                return {'error': 'Missing required fields: customer_id, shipping_address'}, 400

            partner = request.env['res.partner'].sudo().browse(int(customer_id))
            if not partner.exists():
                return {'error': 'Customer not found'}, 404

            existing_shipping_address = partner.child_ids.filtered(lambda c: c.type == 'delivery')[:1]

            values = {
                'parent_id': partner.id,
                'type': 'delivery',
                'name': shipping_address.get('name', partner.name),
                'street': shipping_address.get('street'),
                'street2': shipping_address.get('street2'),
                'city': shipping_address.get('city'),
                'state_id': shipping_address.get('state_id'),
                'country_id': shipping_address.get('country_id'),
                'zip': shipping_address.get('zip'),
                'phone': shipping_address.get('phone'),
                'email': shipping_address.get('email'),
                'company_type': 'person',
            }

            values = {k: v for k, v in values.items() if v is not None}

            if existing_shipping_address:
                existing_shipping_address.write(values)

                return {
                    'status': 'Success',
                    'message': 'Shipping address updated successfully',
                    'shipping_address_id': existing_shipping_address.id
                }
            else:
                new_shipping_address = request.env['res.partner'].sudo().create(values)

                return {
                    'status': 'Success',
                    'message': 'Shipping address added successfully',
                    'shipping_address_id': new_shipping_address.id
                }

        except Exception as e:
            return {'error': str(e)}, 500
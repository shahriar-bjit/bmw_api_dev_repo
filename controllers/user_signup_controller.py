from odoo import http, _
from odoo.http import request
import jwt
import datetime
import secrets
import string
from werkzeug.exceptions import Unauthorized

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

            email_body = f"""Dear {user_name},<br><br>

                        Your account has been created successfully.<br><br>
                        
                        Login: {user.login}<br>
                        Current Password: {password}<br>
                        Reset Password Link: {api_reset_link}<br><br>
                        
                        Please change your password ASAP for security reasons.<br><br>
                        
                        Best regards,<br>
                        The Platform Team"""

            from_email = admin_env.company.email or 'noreply@company.com'

            mail_values = {
                'subject': 'Account Created - Login Details',
                'body_html': email_body,
                'email_to': user.email,
                'email_from': from_email,
                'auto_delete': True,
            }

            mail = admin_env['mail.mail'].sudo().create(mail_values)
            mail.send()
            print("Simple login email sent")

            try:
                user.action_reset_password()
                print("Password reset email sent via Odoo's built-in system")
            except Exception as reset_err:
                print(f"Password reset email failed: {reset_err}")

            return True

        except Exception as e:
            print(f"Email sending failed: {e}")
            import traceback
            print(f"Email error traceback: {traceback.format_exc()}")
            return False

    @http.route('/api/signup', type='json', auth='none', methods=['POST'], csrf=False, cors='*')
    def signup_user(self, **kwargs):
        new_user = None
        try:
            name = kwargs.get('name')
            email = kwargs.get('email')
            phone = kwargs.get('phone')

            if not name and not email:
                return {'error': 'Missing required fields: name, email'}, 400

            if '@' not in email:
                return {'error': 'Invalid email format'}, 400

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
            # company = admin_user.company_id
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
                if phone:
                    partner_updates['phone'] = phone

                partner.sudo().write(partner_updates)

            except Exception as partner_err:
                print(f"Partner update error: {partner_err}")
                if new_user:
                    try:
                        new_user.sudo().unlink()
                    except Exception as cleanup_err:
                        print(f"User cleanup failed: {cleanup_err}")
                return {'error': f'Partner update failed: {str(partner_err)}'}, 500

            token = None
            try:
                secret_key = admin_env['ir.config_parameter'].sudo().get_param('jwt.secret_key') or 'odoo_default_secret'
                expiration = datetime.datetime.utcnow() + datetime.timedelta(hours=24)
                payload = {
                    'user_id': new_user.id,
                    'email': email,
                    'exp': expiration
                }
                token = jwt.encode(payload, secret_key, algorithm='HS256')
            except Exception as jwt_err:
                print(f"JWT generation failed: {jwt_err}")

            try:
                self._send_login_email(admin_env, new_user, generated_password, name)
                email_sent = True
            except Exception as email_err:
                email_sent = False

            try:
                admin_env.cr.commit()
            except Exception as commit_err:
                print(f"Commit failed: {commit_err}")
            verification_user = admin_env['res.users'].sudo().search([('login', '=', email)], limit=1)
            if not verification_user:
                return {'error': 'User created but not findable - possible database issue'}, 500

            return {
                'success': True,
                'message': f'Account created successfully for {name}',
                'customer_id': partner.id,
                'user_id': new_user.id,
                'token': token,
                'login_email': email,
                'generated_password': generated_password,
                'email_sent': email_sent,
                'user_share': new_user.share,
                'user_groups': new_user.groups_id.mapped('name')
            }

        except Exception as e:
            if new_user:
                new_user.sudo().unlink()

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
            admin_env.cr.commit()

            return {
                'success': True,
                'message': 'Password changed successfully! You can now login with your new password.',
                'user_id': user.id,
                'login_email': user.email,
                'login_url': f"{self._get_base_url(request)}/web/login"
            }

        except Exception as e:
            return {'error': f'Password change failed: {str(e)}'}, 500
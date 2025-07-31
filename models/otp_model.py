from odoo import models, fields, api
import random
import string
from datetime import datetime, timedelta

class CustomerOTP(models.Model):
    _name = 'customer.otp'
    _description = 'Customer OTP Verification'

    email = fields.Char(required=True, index=True)
    otp = fields.Char(required=True)
    expiration_time = fields.Datetime(required=True)
    is_verified = fields.Boolean(default=False)

    @api.model
    def generate_otp(self, email):
        self.env['customer.otp'].search([('email', '=', email)]).unlink()
        otp_code = ''.join(random.choices(string.digits, k=6))
        expiration = datetime.now() + timedelta(minutes=5)
        otp_record = self.create({'email': email, 'otp': otp_code, 'expiration_time': expiration})
        return otp_record

    def validate_otp(self, email, otp):
        otp_record = self.search([('email', '=', email), ('otp', '=', otp), ('expiration_time', '>', datetime.now())], limit=1)

        if otp_record:
            otp_record.write({'is_verified': True})
            return True
        return False
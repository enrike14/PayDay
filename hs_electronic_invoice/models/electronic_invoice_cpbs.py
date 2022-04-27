# -*- coding: utf-8 -*-

from dataclasses import field
from email.policy import default
from odoo import models, fields, api
from datetime import datetime


class electronic_invoice_cpbs(models.Model):
	_name = "electronic.invoice.cpbs"
	segmento =  fields.Char(string="Segmento")
	familia =  fields.Char(string="Familia")
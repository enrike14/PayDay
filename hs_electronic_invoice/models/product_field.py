from dataclasses import field
from email.policy import default
from odoo import models, fields, api
from datetime import datetime


class product_field(models.Model):
	#_inherit = "product.product"
	_inherit = "product.template"
	mensaje_codigo='Codigos tipo:\nGTIN – 14 (14 caracteres)\nGTIN – 13 (13 caracteres)\nGTIN – 12 (12 caracteres)\nGTIN – 8 (8 caracteres)'
	#asignar campos al modulo de product.product
	categoryProduct = fields.Selection(
	[('Sin Categoría', 'Sin Categoría'),
	('Materia prima Farmacéutica', 'Materia prima Farmacéutica'),
	('Medicina', 'Medicina'),
	('Alimento', 'Alimento')],string = 'Categoría del Producto')
	fechaFabricacion = fields.Date(string='Fecha de Fabricación')
	fechaCaducidad = fields.Date(string='Fecha de Caducidad')
	codigoCPBSAbrev = fields.Char(string="Código CPBS Abrev")
	codigoCPBS = fields.Char(string="Código CPBS")
	unidadMedidaCPBS = fields.Char(string="Unidad de Medida CPBS")
	codigoGTIN = fields.Char(string="Código GTIN",size=14,help=mensaje_codigo)
	codigoGTINInv = fields.Char(string="Código GTIN para la unidad de inventario",size=14,help=mensaje_codigo)
	
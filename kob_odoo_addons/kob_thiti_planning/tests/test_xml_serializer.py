from lxml import etree

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "thiti")
class TestXmlSerializer(TransactionCase):

    def setUp(self):
        super().setUp()
        self.ser = self.env["thiti.xml.serializer"]

    def test_serialize_empty(self):
        data = {"current": None, "_counts": {}}
        xml = self.ser.serialize(data)
        self.assertTrue(xml.startswith(b"<?xml"))
        root = etree.fromstring(xml.replace(b"<?python", b"<!--").replace(b"?>", b"-->"))
        self.assertEqual(root.tag, "plan")

    def test_serialize_items_emits_each(self):
        data = {
            "items": [{"name": "ITEM-A", "description": "Item A", "cost": 10.0},
                      {"name": "ITEM-B", "description": "Item B", "cost": 20.0}],
        }
        xml = self.ser.serialize(data)
        self.assertIn(b"<name>ITEM-A</name>", xml)
        self.assertIn(b"<name>ITEM-B</name>", xml)

    def test_python_directive_included(self):
        xml = self.ser.serialize({}, plan_type="1", constraint="15")
        self.assertIn(b"frepple.solver_mrp", xml)
        self.assertIn(b"saveplan", xml)

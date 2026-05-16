from odoo.tests import TransactionCase, tagged


SAMPLE_OUTPUT = b"""<?xml version='1.0' encoding='UTF-8'?>
<plan>
  <operationplans>
    <operationplan>
      <reference>OP-1</reference>
      <ordertype>PO</ordertype>
      <quantity>10</quantity>
      <start>2026-06-01T00:00:00</start>
      <end>2026-06-02T00:00:00</end>
      <status>proposed</status>
    </operationplan>
  </operationplans>
  <problems>
    <problem>
      <name>overload</name>
      <severity>warning</severity>
      <weight>5</weight>
      <description>resource X overloaded</description>
    </problem>
  </problems>
</plan>
"""


@tagged("post_install", "-at_install", "thiti")
class TestXmlParser(TransactionCase):

    def setUp(self):
        super().setUp()
        self.parser = self.env["thiti.xml.parser"]
        self.run = self.env["thiti.plan.run"].create({"name": "parser-test"})

    def test_parse_returns_counts(self):
        counts = self.parser.parse(self.run, SAMPLE_OUTPUT)
        self.assertEqual(counts["operations"], 1)
        self.assertEqual(counts["problems"], 1)

    def test_parse_stores_records(self):
        self.parser.parse(self.run, SAMPLE_OUTPUT)
        ops = self.env["thiti.plan.operation"].search([("run_id", "=", self.run.id)])
        self.assertEqual(len(ops), 1)
        self.assertEqual(ops.reference, "OP-1")
        self.assertEqual(ops.op_type, "po")
        self.assertEqual(ops.quantity, 10.0)

    def test_parse_empty_safe(self):
        counts = self.parser.parse(self.run, b"")
        self.assertEqual(counts["operations"], 0)

    def test_parse_clears_previous(self):
        # First run
        self.parser.parse(self.run, SAMPLE_OUTPUT)
        # Second run should replace, not append
        self.parser.parse(self.run, SAMPLE_OUTPUT)
        ops = self.env["thiti.plan.operation"].search([("run_id", "=", self.run.id)])
        self.assertEqual(len(ops), 1)

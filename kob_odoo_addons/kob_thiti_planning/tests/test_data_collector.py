from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "thiti")
class TestDataCollector(TransactionCase):

    def setUp(self):
        super().setUp()
        self.collector = self.env["thiti.data.collector"]
        self.run = self.env["thiti.plan.run"].create({
            "name": "test-collector",
            "plan_horizon_days": 30,
        })

    def test_collect_returns_required_keys(self):
        data = self.collector.collect(self.run)
        for key in ("items", "locations", "demands", "buffers",
                    "resources", "operations", "_counts"):
            self.assertIn(key, data)

    def test_collect_counts_match_lists(self):
        data = self.collector.collect(self.run)
        counts = data["_counts"]
        self.assertEqual(counts["items"], len(data["items"]))
        self.assertEqual(counts["demands"], len(data["demands"]))

    def test_collect_horizon_applied(self):
        data = self.collector.collect(self.run)
        self.assertIsNotNone(data.get("current"))
        self.assertIsNotNone(data.get("horizon_end"))
        self.assertGreater(data["horizon_end"], data["current"])

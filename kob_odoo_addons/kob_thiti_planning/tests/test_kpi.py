from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "thiti")
class TestKpi(TransactionCase):

    def test_kpi_defaults_empty(self):
        run = self.env["thiti.plan.run"].create({"name": "kpi-1"})
        kpi = self.env["thiti.kpi"].recompute_for_run(run)
        self.assertEqual(kpi.total_demands, 0)
        # 0/0 demands → service level defaults to 100%
        self.assertEqual(kpi.service_level_pct, 100.0)
        self.assertEqual(kpi.problem_critical, 0)

    def test_kpi_upsert(self):
        run = self.env["thiti.plan.run"].create({"name": "kpi-2"})
        first = self.env["thiti.kpi"].recompute_for_run(run)
        second = self.env["thiti.kpi"].recompute_for_run(run)
        self.assertEqual(first.id, second.id, "recompute must upsert, not duplicate")

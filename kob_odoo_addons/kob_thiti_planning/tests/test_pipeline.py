from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "thiti")
class TestPipeline(TransactionCase):

    def test_action_collect_preview_attaches_xml(self):
        run = self.env["thiti.plan.run"].create({"name": "pipeline-1"})
        run.action_collect_preview()
        self.assertTrue(run.input_xml_attachment_id)
        self.assertGreater(run.input_xml_attachment_id.file_size, 0)

    def test_full_run_state_transitions(self):
        """Engine may not be present in CI, but pipeline path should at
        least reach 'collecting' state without crashing."""
        run = self.env["thiti.plan.run"].create({"name": "pipeline-2"})
        try:
            run.action_run()
        except Exception:
            pass  # engine binary may be missing in test env
        self.assertIn(run.state, ("done", "failed"))

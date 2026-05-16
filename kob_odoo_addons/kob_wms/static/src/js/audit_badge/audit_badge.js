/** @odoo-module **/
/* eslint-disable */
/*
 * KOB WMS — Audit Badge widget
 *
 * 3-way hash compare badge for wms.sales.order. Renders VERIFIED /
 * TAMPERED / DIVERGED / NOT_IN_BOAT / BOAT_OFFLINE / UNSEALED state
 * after calling /kob/api/audit/sales_order/<id>. Manager can trigger
 * "Re-sync from Boat" recovery from the badge.
 *
 * Drop on a form view:
 *   <field name="audit_hash" widget="kob_audit_badge"/>
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";

const RESULT_META = {
    VERIFIED:     { label: "Verified",     css: "verified",   icon: "fa-check-circle"  },
    DIVERGED:     { label: "Diverged",     css: "diverged",   icon: "fa-random"        },
    TAMPERED:     { label: "Tampered",     css: "tampered",   icon: "fa-exclamation-triangle" },
    UNSEALED:     { label: "Unsealed",     css: "unsealed",   icon: "fa-circle-o"      },
    NOT_IN_BOAT:  { label: "Not in Boat",  css: "noboat",     icon: "fa-question"      },
    BOAT_OFFLINE: { label: "Boat Offline", css: "offline",    icon: "fa-plug"          },
    ERROR:        { label: "Error",        css: "error",      icon: "fa-times"         },
};

export class KobAuditBadge extends Component {
    static template = "kob_wms.AuditBadge";
    static props = { ...standardFieldProps };

    setup() {
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            result: "UNSEALED",
            hash_short: "",
            sealed_at: false,
            message: "",
            recovering: false,
        });
        onWillStart(async () => {
            await this.refresh();
        });
    }

    get orderId() {
        return this.props.record.resId;
    }

    get meta() {
        return RESULT_META[this.state.result] || RESULT_META.ERROR;
    }

    get canRecover() {
        return ["TAMPERED", "DIVERGED"].includes(this.state.result);
    }

    async refresh() {
        if (!this.orderId) {
            this.state.loading = false;
            return;
        }
        this.state.loading = true;
        try {
            const res = await rpc(
                `/kob/api/audit/sales_order/${this.orderId}`,
                {},
            );
            Object.assign(this.state, {
                result: res.result || "ERROR",
                hash_short: res.hash_short || "",
                sealed_at: res.sealed_at || false,
                message: res.message || "",
            });
        } catch (err) {
            this.state.result = "ERROR";
            this.state.message = err.message || "rpc_failed";
        } finally {
            this.state.loading = false;
        }
    }

    async onRecover() {
        if (!this.canRecover || this.state.recovering) {
            return;
        }
        const confirmMsg = _t(
            "Re-sync this order from Boat? KOB data will be overwritten " +
            "with the Boat (kiss-production) values and hash re-sealed."
        );
        if (!window.confirm(confirmMsg)) {
            return;
        }
        this.state.recovering = true;
        try {
            const res = await rpc(
                `/kob/api/audit/recover/sales_order/${this.orderId}`,
                {},
            );
            if (res.result === "ERROR") {
                this.notification.add(
                    _t("Recovery failed: ") + (res.message || ""),
                    { type: "danger" },
                );
            } else {
                this.notification.add(
                    _t("Recovered from Boat. New hash: ") + (res.hash_short || ""),
                    { type: "success" },
                );
                await this.refresh();
            }
        } catch (err) {
            this.notification.add(
                _t("Recovery error: ") + (err.message || ""),
                { type: "danger" },
            );
        } finally {
            this.state.recovering = false;
        }
    }
}

registry.category("fields").add("kob_audit_badge", {
    component: KobAuditBadge,
});

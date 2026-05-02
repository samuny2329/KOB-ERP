/** @odoo-module **/
/* eslint-disable */
/**
 * Force every datetime field to render with the user's lang full format
 * (date_format + " " + time_format), e.g. "02/05/2026 18:52:53".
 *
 * Odoo 19 default: Luxon DATETIME_SHORT (locale-aware 12h) → "May 2, 4:41 PM"
 * KOB override:    localization.dateTimeFormat → "02/05/2026 18:52:53"
 */
import { localization } from "@web/core/l10n/localization";
import { patch } from "@web/core/utils/patch";
import * as dates from "@web/core/l10n/dates";

const _origFormatDateTime = dates.formatDateTime;

patch(dates, {
    formatDateTime(value, options = {}) {
        if (!value) return "";
        // Force full lang format unless caller explicitly passed a different format
        const opts = { ...options };
        if (!opts.format) {
            opts.format = localization.dateTimeFormat;
        }
        // Disable any "condensed" / "tz" that compresses display
        opts.condensed = false;
        return _origFormatDateTime(value, opts);
    },
});

/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";

/**
 * Embeds the Listing Radio HTML app inside the Odoo backend so the standard
 * navbar and app switcher remain available.
 */
export class ListingAppAction extends Component {
    static template = "chc_radio_listing.ListingAppAction";
    static props = { "*": true };

    setup() {
        this.appUrl = "/chc_radio_listing/app";
    }

    get rootClass() {
        return ["o_chc_radio_listing_action", this.props.className || "o_action"]
            .filter(Boolean)
            .join(" ");
    }
}

registry.category("actions").add("chc_radio_listing.listing_app", ListingAppAction);

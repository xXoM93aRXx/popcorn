/** @odoo-module **/

import { registry } from "@web/core/registry";
import { PopcornSignatureDialog } from "./popcorn_signature_dialog";

// Register the client action
registry.category("actions").add("popcorn_signature_dialog", function (env, action) {
    const contractId = action.context.contract_id;
    
    env.services.dialog.add(PopcornSignatureDialog, {
        contractId: contractId,
    });
});
/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";
import { Dialog } from "@web/core/dialog/dialog";
import { Component, onMounted, useRef, useState } from "@odoo/owl";

export class PopcornSignatureDialog extends Component {
    static template = "popcorn.PopcornSignatureDialog";
    static components = { Dialog };
    static props = {
        contractId: Number,
        close: Function,
    };

    setup() {
        this.state = useState({
            isSignatureEmpty: true,
        });

        this.canvasRef = useRef("signatureCanvas");
        this.isDrawing = false;
        this.lastX = 0;
        this.lastY = 0;

        onMounted(() => {
            this.initCanvas();
        });
    }

    initCanvas() {
        const canvas = this.canvasRef.el;
        if (!canvas) return;

        this.ctx = canvas.getContext("2d");
        this.ctx.strokeStyle = "#000000";
        this.ctx.lineWidth = 2;
        this.ctx.lineCap = "round";
        this.ctx.lineJoin = "round";

        // Mouse events
        canvas.addEventListener("mousedown", this.startDrawing.bind(this));
        canvas.addEventListener("mousemove", this.draw.bind(this));
        canvas.addEventListener("mouseup", this.stopDrawing.bind(this));
        canvas.addEventListener("mouseout", this.stopDrawing.bind(this));

        // Touch events for mobile
        canvas.addEventListener("touchstart", this.handleTouchStart.bind(this));
        canvas.addEventListener("touchmove", this.handleTouchMove.bind(this));
        canvas.addEventListener("touchend", this.stopDrawing.bind(this));
    }

    startDrawing(e) {
        this.isDrawing = true;
        const rect = this.canvasRef.el.getBoundingClientRect();
        this.lastX = e.clientX - rect.left;
        this.lastY = e.clientY - rect.top;
        this.state.isSignatureEmpty = false;
    }

    draw(e) {
        if (!this.isDrawing) return;

        const rect = this.canvasRef.el.getBoundingClientRect();
        const currentX = e.clientX - rect.left;
        const currentY = e.clientY - rect.top;

        this.ctx.beginPath();
        this.ctx.moveTo(this.lastX, this.lastY);
        this.ctx.lineTo(currentX, currentY);
        this.ctx.stroke();

        this.lastX = currentX;
        this.lastY = currentY;
    }

    stopDrawing() {
        this.isDrawing = false;
    }

    handleTouchStart(e) {
        e.preventDefault();
        const touch = e.touches[0];
        const rect = this.canvasRef.el.getBoundingClientRect();
        this.isDrawing = true;
        this.lastX = touch.clientX - rect.left;
        this.lastY = touch.clientY - rect.top;
        this.state.isSignatureEmpty = false;
    }

    handleTouchMove(e) {
        if (!this.isDrawing) return;
        e.preventDefault();

        const touch = e.touches[0];
        const rect = this.canvasRef.el.getBoundingClientRect();
        const currentX = touch.clientX - rect.left;
        const currentY = touch.clientY - rect.top;

        this.ctx.beginPath();
        this.ctx.moveTo(this.lastX, this.lastY);
        this.ctx.lineTo(currentX, currentY);
        this.ctx.stroke();

        this.lastX = currentX;
        this.lastY = currentY;
    }

    onClickClear() {
        const canvas = this.canvasRef.el;
        if (canvas && this.ctx) {
            this.ctx.clearRect(0, 0, canvas.width, canvas.height);
            this.state.isSignatureEmpty = true;
        }
    }

    async onClickConfirm() {
        if (this.state.isSignatureEmpty) {
            this.env.services.notification.add(_t("Please provide a signature"), {
                type: "warning",
            });
            return;
        }

        try {
            // Get the signature as base64 image
            const canvas = this.canvasRef.el;
            const signatureDataURL = canvas.toDataURL("image/png");
            
            // Remove the data URL prefix to get just the base64 data
            const signatureData = signatureDataURL.replace(/^data:image\/png;base64,/, "");

            // Call the controller to save the signature
            const result = await rpc("/popcorn/contract/sign_customer", {
                contract_id: this.props.contractId,
                signature_data: signatureData,
            });

            if (result.success || result === true) {
                this.env.services.notification.add(_t("Contract signed successfully!"), {
                    type: "success",
                });
                
                // Reload the current view
                await this.env.services.action.doAction({
                    type: 'ir.actions.client',
                    tag: 'reload',
                });
                
                // Close the dialog
                this.props.close();
            } else {
                this.env.services.notification.add(_t("Error signing contract: %s", result.error || "Unknown error"), {
                    type: "danger",
                });
            }
        } catch (error) {
            console.error("Error signing contract:", error);
            this.env.services.notification.add(_t("Error signing contract"), {
                type: "danger",
            });
        }
    }

    onClickCancel() {
        this.props.close();
    }
}
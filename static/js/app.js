const forms = document.querySelectorAll("[data-sale-form]");

forms.forEach((form) => {
    const unitsInput = form.querySelector('input[name="units_count"]');
    const originalInput = form.querySelector('input[name="original_price_per_unit"]');
    const discountInput = form.querySelector('input[name="discount_per_unit"]');
    const commissionInput = form.querySelector('input[name="commission_per_unit"]');
    const adminExpenseInput = form.querySelector('input[name="admin_expense"]');
    const previewRoot = form.closest(".panel")?.querySelector("[data-sale-preview]");

    const renderPreview = () => {
        if (!previewRoot || !unitsInput || !originalInput || !discountInput) {
            return;
        }

        const units = Number(unitsInput.value || 0);
        const originalPrice = Number(originalInput.value || 0);
        const discount = Number(discountInput.value || 0);
        const commission = Number(commissionInput?.value || 0);
        const adminExpense = Number(adminExpenseInput?.value || 0);
        const unitPrice = Math.max(originalPrice - discount, 0);
        const totalPrice = unitPrice * units;
        const finalPrice = form.dataset.saleForm === "retail"
            ? totalPrice + (commission * units) + adminExpense
            : totalPrice;

        previewRoot.querySelector('[data-preview="unit_price"]').textContent = unitPrice.toFixed(2);
        previewRoot.querySelector('[data-preview="final_price"]').textContent = finalPrice.toFixed(2);
    };

    ["input", "change"].forEach((eventName) => {
        form.addEventListener(eventName, renderPreview);
    });
    renderPreview();
});

document.querySelectorAll("[data-stock-pick]").forEach((button) => {
    button.addEventListener("click", () => {
        const form = document.querySelector('[data-sale-form="retail"]');
        if (!form) {
            return;
        }

        const fruitInput = form.querySelector('[data-sale-field="fruit"]');
        const classInput = form.querySelector('[data-sale-field="class"]');
        const priceInput = form.querySelector('[data-sale-field="price"]');

        if (fruitInput) {
            fruitInput.value = button.dataset.fruit || "";
        }
        if (classInput) {
            classInput.value = button.dataset.class || "";
        }
        if (priceInput) {
            priceInput.value = button.dataset.price || "";
        }

        form.dispatchEvent(new Event("input", { bubbles: true }));
    });
});

document.querySelectorAll("[data-confirm]").forEach((button) => {
    button.addEventListener("click", (event) => {
        const message = button.getAttribute("data-confirm");
        if (!window.confirm(message)) {
            event.preventDefault();
        }
    });
});

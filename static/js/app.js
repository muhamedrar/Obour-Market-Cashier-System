const forms = document.querySelectorAll("[data-sale-form]");

forms.forEach((form) => {
    const unitsInput = form.querySelector('input[name="units_count"]');
    const originalInput = form.querySelector('input[name="original_price_per_unit"]');
    const discountInput = form.querySelector('input[name="discount_per_unit"]');
    const commissionInput = form.querySelector('input[name="commission_per_unit"]');
    const adminExpenseInput = form.querySelector('input[name="admin_expense"]');
    const previewRoot = form.closest(".panel")?.querySelector("[data-sale-preview]");
    const priceDisplay = form.querySelector("[data-sale-price-display]");
    const fruitField = form.querySelector('[data-sale-field="fruit"]');
    const classField = form.querySelector('[data-sale-field="class"]');
    const stockOptions = JSON.parse(form.dataset.stockOptions || "[]");

    const setSelectOptions = (field, values, placeholder, selectedValue = "") => {
        if (!field) {
            return;
        }

        const uniqueValues = [...new Set(values.filter(Boolean))];
        field.innerHTML = "";

        const placeholderOption = document.createElement("option");
        placeholderOption.value = "";
        placeholderOption.textContent = placeholder;
        field.appendChild(placeholderOption);

        uniqueValues.forEach((value) => {
            const option = document.createElement("option");
            option.value = value;
            option.textContent = value;
            if (value === selectedValue) {
                option.selected = true;
            }
            field.appendChild(option);
        });

        if (selectedValue && !uniqueValues.includes(selectedValue)) {
            const option = document.createElement("option");
            option.value = selectedValue;
            option.textContent = selectedValue;
            option.selected = true;
            field.appendChild(option);
        }

        if (!selectedValue) {
            field.value = "";
        }
    };

    const syncClassOptions = () => {
        if (!fruitField || !classField) {
            return;
        }

        const selectedFruit = fruitField.value;
        const currentClass = classField.value;
        const classValues = stockOptions
            .filter((item) => item.fruit_name === selectedFruit)
            .map((item) => item.class_number);

        const nextClass = classValues.includes(currentClass)
            ? currentClass
            : (classValues[0] || currentClass);

        setSelectOptions(classField, classValues, "اختر الدرجة", nextClass);
    };

    const updateOriginalPrice = () => {
        if (!originalInput || !fruitField || !classField) {
            return;
        }

        const selectedFruit = fruitField.value;
        const selectedClass = classField.value;
        const unitsNeeded = Number(unitsInput?.value || 0);
        const matchingLots = stockOptions.filter(
            (item) => item.fruit_name === selectedFruit && item.class_number === selectedClass
        );

        if (!matchingLots.length) {
            originalInput.value = "";
            return;
        }

        const requestedUnits = unitsNeeded > 0 ? unitsNeeded : 1;
        let remainingUnits = requestedUnits;
        let supplierTotal = 0;

        matchingLots.forEach((item) => {
            if (remainingUnits <= 0) {
                return;
            }

            const consumedUnits = Math.min(Number(item.remaining_units || 0), remainingUnits);
            supplierTotal += consumedUnits * Number(item.price_per_unit || 0);
            remainingUnits -= consumedUnits;
        });

        const effectiveUnits = requestedUnits - remainingUnits;
        if (effectiveUnits <= 0) {
            originalInput.value = "";
            return;
        }

        originalInput.value = (supplierTotal / effectiveUnits).toFixed(2);
    };

    if (fruitField && classField) {
        const currentFruit = fruitField.value;
        const currentClass = classField.value;
        setSelectOptions(
            fruitField,
            stockOptions.map((item) => item.fruit_name),
            "اختر الصنف من المخزون",
            currentFruit
        );
        syncClassOptions();
        if (currentClass && classField.value !== currentClass) {
            setSelectOptions(
                classField,
                stockOptions
                    .filter((item) => item.fruit_name === fruitField.value)
                    .map((item) => item.class_number),
                "اختر الدرجة",
                currentClass
            );
        }
    }

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

        if (priceDisplay) {
            priceDisplay.textContent = originalPrice > 0
                ? `${originalPrice.toFixed(2)} ج.م`
                : "يتم جلبه تلقائياً من بيانات المورد";
        }
        previewRoot.querySelector('[data-preview="unit_price"]').textContent = unitPrice.toFixed(2);
        previewRoot.querySelector('[data-preview="final_price"]').textContent = finalPrice.toFixed(2);
    };

    ["input", "change"].forEach((eventName) => {
        form.addEventListener(eventName, renderPreview);
    });
    fruitField?.addEventListener("change", () => {
        syncClassOptions();
        updateOriginalPrice();
        renderPreview();
    });
    classField?.addEventListener("change", () => {
        updateOriginalPrice();
        renderPreview();
    });
    unitsInput?.addEventListener("input", () => {
        updateOriginalPrice();
        renderPreview();
    });
    updateOriginalPrice();
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
            fruitInput.dispatchEvent(new Event("change", { bubbles: true }));
        }
        if (classInput) {
            classInput.value = button.dataset.class || "";
            classInput.dispatchEvent(new Event("change", { bubbles: true }));
        }
        if (priceInput) {
            priceInput.value = button.dataset.price || "";
        }
        const priceDisplay = form.querySelector("[data-sale-price-display]");
        if (priceDisplay) {
            priceDisplay.textContent = button.dataset.price
                ? `${Number(button.dataset.price).toFixed(2)} ج.م`
                : "يتم جلبه تلقائياً من بيانات المورد";
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

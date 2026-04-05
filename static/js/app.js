const forms = document.querySelectorAll("[data-sale-form]");

forms.forEach((form) => {
    const unitsInput = form.querySelector('input[name="units_count"]');
    const originalInput = form.querySelector('input[name="original_price_per_unit"]');
    const discountInput = form.querySelector('input[name="discount_per_unit"]');
    const discountModeInput = form.querySelector('[name="discount_mode"]');
    const commissionInput = form.querySelector('input[name="commission_per_unit"]');
    const adminExpenseInput = form.querySelector('input[name="admin_expense"]');
    const previewRoot = form.closest(".panel")?.querySelector("[data-sale-preview]");
    const previewLabel = previewRoot?.querySelector("[data-preview-label]");
    const priceDisplay = form.querySelector("[data-sale-price-display]");
    const fruitField = form.querySelector('[data-sale-field="fruit"]');
    const classField = form.querySelector('[data-sale-field="class"]');
    const kilogramsField = form.querySelector('[data-sale-field="kilograms"]');
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

    const syncKilogramsOptions = () => {
        if (!fruitField || !classField || !kilogramsField) {
            return;
        }

        const selectedFruit = fruitField.value;
        const selectedClass = classField.value;
        const currentKilograms = kilogramsField.value;
        const kilogramValues = stockOptions
            .filter(
                (item) => item.fruit_name === selectedFruit && item.class_number === selectedClass
            )
            .map((item) => Number(item.kilograms_per_unit || 0).toFixed(2));

        const nextKilograms = kilogramValues.includes(currentKilograms)
            ? currentKilograms
            : (kilogramValues[0] || currentKilograms);

        setSelectOptions(kilogramsField, kilogramValues, "اختر الوزن", nextKilograms);
    };

    const updateOriginalPrice = () => {
        if (!originalInput || !fruitField || !classField || !kilogramsField) {
            return;
        }

        const selectedFruit = fruitField.value;
        const selectedClass = classField.value;
        const selectedKilograms = Number(kilogramsField.value || 0).toFixed(2);
        const unitsNeeded = Number(unitsInput?.value || 0);
        const matchingLots = stockOptions.filter(
            (item) =>
                item.fruit_name === selectedFruit &&
                item.class_number === selectedClass &&
                Number(item.kilograms_per_unit || 0).toFixed(2) === selectedKilograms
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
        const currentKilograms = kilogramsField?.value || "";
        setSelectOptions(
            fruitField,
            stockOptions.map((item) => item.fruit_name),
            "اختر الصنف من المخزون",
            currentFruit
        );
        syncClassOptions();
        syncKilogramsOptions();
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
        if (kilogramsField && currentKilograms && kilogramsField.value !== currentKilograms) {
            setSelectOptions(
                kilogramsField,
                stockOptions
                    .filter(
                        (item) =>
                            item.fruit_name === fruitField.value &&
                            item.class_number === classField.value
                    )
                    .map((item) => Number(item.kilograms_per_unit || 0).toFixed(2)),
                "اختر الوزن",
                currentKilograms
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
        const discountMode = discountModeInput?.value === "unit_price" ? "unit_price" : "commission";
        const commission = Number(commissionInput?.value || 0);
        const adminExpense = Number(adminExpenseInput?.value || 0);
        const unitPrice = discountMode === "unit_price"
            ? Math.max(originalPrice - discount, 0)
            : originalPrice;
        const netCommission = discountMode === "commission"
            ? Math.max(commission - discount, 0)
            : commission;
        const totalPrice = unitPrice * units;
        const finalPrice = totalPrice + (netCommission * units) + adminExpense;

        if (priceDisplay) {
            priceDisplay.textContent = originalPrice > 0
                ? `${originalPrice.toFixed(2)} ج.م`
                : "يتم جلبه تلقائياً من بيانات المورد";
        }
        if (previewLabel) {
            previewLabel.textContent = discountMode === "commission"
                ? "العمولة الصافية للوحدة"
                : "سعر البيع للوحدة";
        }
        previewRoot.querySelector('[data-preview="unit_price"]').textContent = (
            discountMode === "commission" ? netCommission : unitPrice
        ).toFixed(2);
        previewRoot.querySelector('[data-preview="final_price"]').textContent = finalPrice.toFixed(2);
    };

    ["input", "change"].forEach((eventName) => {
        form.addEventListener(eventName, renderPreview);
    });
    fruitField?.addEventListener("change", () => {
        syncClassOptions();
        syncKilogramsOptions();
        updateOriginalPrice();
        renderPreview();
    });
    classField?.addEventListener("change", () => {
        syncKilogramsOptions();
        updateOriginalPrice();
        renderPreview();
    });
    kilogramsField?.addEventListener("change", () => {
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
        const kilogramsInput = form.querySelector('[data-sale-field="kilograms"]');
        const priceInput = form.querySelector('[data-sale-field="price"]');

        if (fruitInput) {
            fruitInput.value = button.dataset.fruit || "";
            fruitInput.dispatchEvent(new Event("change", { bubbles: true }));
        }
        if (classInput) {
            classInput.value = button.dataset.class || "";
            classInput.dispatchEvent(new Event("change", { bubbles: true }));
        }
        if (kilogramsInput) {
            kilogramsInput.value = button.dataset.kilograms || "";
            kilogramsInput.dispatchEvent(new Event("change", { bubbles: true }));
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

document.querySelectorAll("[data-supplier-form]").forEach((form) => {
    const kilogramsPerUnitInput = form.querySelector('input[name="kilograms_per_unit"]');
    const pricePerKilogramInput = form.querySelector('input[name="price_per_kilogram"]');
    const pricePerUnitInput = form.querySelector('input[name="price_per_unit"]');

    const syncUnitPrice = () => {
        if (!kilogramsPerUnitInput || !pricePerKilogramInput || !pricePerUnitInput) {
            return;
        }

        const kilogramsPerUnit = Number(kilogramsPerUnitInput.value || 0);
        const pricePerKilogram = Number(pricePerKilogramInput.value || 0);

        if (kilogramsPerUnit > 0 && pricePerKilogram > 0) {
            pricePerUnitInput.value = (kilogramsPerUnit * pricePerKilogram).toFixed(2);
            return;
        }

        pricePerUnitInput.value = "";
    };

    kilogramsPerUnitInput?.addEventListener("input", syncUnitPrice);
    pricePerKilogramInput?.addEventListener("input", syncUnitPrice);
    syncUnitPrice();
});

const actionDialogs = document.querySelectorAll("[data-action-dialog]");

const closeDialog = (dialog) => {
    if (!dialog) {
        return;
    }

    if (typeof dialog.close === "function" && dialog.open) {
        dialog.close();
        return;
    }

    dialog.removeAttribute("open");
};

const openDialog = (dialog) => {
    if (!dialog) {
        return;
    }

    actionDialogs.forEach((otherDialog) => {
        if (otherDialog !== dialog) {
            closeDialog(otherDialog);
        }
    });

    if (dialog.open) {
        return;
    }

    if (typeof dialog.showModal === "function") {
        dialog.showModal();
        return;
    }

    dialog.setAttribute("open", "open");
};

document.querySelectorAll("[data-open-dialog]").forEach((button) => {
    button.addEventListener("click", () => {
        const dialogId = button.getAttribute("data-open-dialog");
        const dialog = dialogId ? document.getElementById(dialogId) : null;

        openDialog(dialog);
    });
});

document.querySelectorAll("[data-close-dialog]").forEach((button) => {
    button.addEventListener("click", () => {
        const dialog = button.closest("[data-action-dialog]");
        closeDialog(dialog);
    });
});

actionDialogs.forEach((dialog) => {
    dialog.addEventListener("click", (event) => {
        const bounds = dialog.getBoundingClientRect();
        const clickedBackdrop = (
            event.clientX < bounds.left ||
            event.clientX > bounds.right ||
            event.clientY < bounds.top ||
            event.clientY > bounds.bottom
        );

        if (clickedBackdrop && dialog.open) {
            closeDialog(dialog);
        }
    });
});

const shiftCutoffRoot = document.body;
const shiftStart = shiftCutoffRoot?.dataset.shiftStart;
const shiftEnd = shiftCutoffRoot?.dataset.shiftEnd;
const shiftCutoff = shiftCutoffRoot?.dataset.shiftCutoff;

if (shiftStart && shiftEnd && shiftCutoff) {
    document.querySelectorAll('form[method="get"]').forEach((form) => {
        const dateFromInput = form.querySelector('input[name="date_from"]');
        const dateToInput = form.querySelector('input[name="date_to"]');

        if (!dateFromInput || !dateToInput || form.querySelector("[data-shift-cutoff-trigger]")) {
            return;
        }

        const button = document.createElement("button");
        button.type = "button";
        button.className = "btn btn-ghost";
        button.dataset.shiftCutoffTrigger = "true";
        button.textContent = `وردية ${shiftCutoff}`;
        button.title = `تطبيق فترة الوردية الحالية من ${shiftStart} إلى ${shiftEnd}`;
        button.addEventListener("click", () => {
            dateFromInput.value = shiftStart;
            dateToInput.value = shiftEnd;
            form.requestSubmit();
        });
        form.appendChild(button);
    });
}

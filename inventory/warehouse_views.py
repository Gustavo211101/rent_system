from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from accounts.permissions import can_edit_inventory, can_view_stock

from .warehouse_forms import StockCategoryForm, StockSubcategoryForm

# Tolerant imports (project may still be transitioning)
try:
    from .models import StockCategory, StockSubcategory, StockItem
except Exception:  # pragma: no cover
    from .models import StockCategory, StockSubcategory
    StockItem = None


@login_required
def stock_category_list_view(request):
    if not can_view_stock(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    categories = StockCategory.objects.all().order_by("name")
    return render(request, "inventory/warehouse/categories/list.html", {
        "categories": categories,
    })


@login_required
def stock_category_add_view(request):
    if not can_edit_inventory(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    if request.method == "POST":
        form = StockCategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Категория добавлена")
            return redirect("stock_category_list")
    else:
        form = StockCategoryForm()

    return render(request, "inventory/warehouse/categories/form.html", {
        "form": form,
        "title": "Добавить категорию",
    })


@login_required
def stock_category_edit_view(request, category_id: int):
    if not can_edit_inventory(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    category = get_object_or_404(StockCategory, id=category_id)

    if request.method == "POST":
        form = StockCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, "Категория обновлена")
            return redirect("stock_category_list")
    else:
        form = StockCategoryForm(instance=category)

    return render(request, "inventory/warehouse/categories/form.html", {
        "form": form,
        "title": "Редактировать категорию",
        "category": category,
    })


@login_required
def stock_category_delete_view(request, category_id: int):
    if not can_edit_inventory(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    category = get_object_or_404(StockCategory, id=category_id)

    # Protect deletion if any subcategories/items exist
    has_subcats = StockSubcategory.objects.filter(category=category).exists()
    has_items = False
    if StockItem is not None:
        has_items = StockItem.objects.filter(subcategory__category=category).exists()

    if request.method == "POST":
        if has_subcats or has_items:
            messages.error(request, "Нельзя удалить категорию: в ней есть подкатегории/оборудование")
            return redirect("stock_category_list")
        category.delete()
        messages.success(request, "Категория удалена")
        return redirect("stock_category_list")

    return render(request, "inventory/warehouse/categories/confirm_delete.html", {
        "category": category,
        "has_subcats": has_subcats,
        "has_items": has_items,
    })


@login_required
def stock_category_detail_view(request, category_id: int):
    if not can_view_stock(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    category = get_object_or_404(StockCategory, id=category_id)
    subcategories = StockSubcategory.objects.filter(category=category).order_by("name")

    return render(request, "inventory/warehouse/subcategories/list.html", {
        "category": category,
        "subcategories": subcategories,
    })


@login_required
def stock_subcategory_add_view(request, category_id: int):
    if not can_edit_inventory(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    category = get_object_or_404(StockCategory, id=category_id)

    if request.method == "POST":
        form = StockSubcategoryForm(request.POST)
        if form.is_valid():
            subcat = form.save(commit=False)
            subcat.category = category
            subcat.save()
            messages.success(request, "Подкатегория добавлена")
            return redirect("stock_category_detail", category_id=category.id)
    else:
        form = StockSubcategoryForm()

    return render(request, "inventory/warehouse/subcategories/form.html", {
        "form": form,
        "title": "Добавить подкатегорию",
        "category": category,
    })


@login_required
def stock_subcategory_edit_view(request, subcategory_id: int):
    if not can_edit_inventory(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    subcategory = get_object_or_404(StockSubcategory, id=subcategory_id)

    if request.method == "POST":
        form = StockSubcategoryForm(request.POST, instance=subcategory)
        if form.is_valid():
            form.save()
            messages.success(request, "Подкатегория обновлена")
            return redirect("stock_category_detail", category_id=subcategory.category.id)
    else:
        form = StockSubcategoryForm(instance=subcategory)

    return render(request, "inventory/warehouse/subcategories/form.html", {
        "form": form,
        "title": "Редактировать подкатегорию",
        "category": subcategory.category,
        "subcategory": subcategory,
    })


@login_required
def stock_subcategory_delete_view(request, subcategory_id: int):
    if not can_edit_inventory(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    subcategory = get_object_or_404(StockSubcategory, id=subcategory_id)

    has_items = False
    if StockItem is not None:
        has_items = StockItem.objects.filter(subcategory=subcategory).exists()

    if request.method == "POST":
        if has_items:
            messages.error(request, "Нельзя удалить подкатегорию: в ней есть оборудование")
            return redirect("stock_category_detail", category_id=subcategory.category.id)
        subcategory.delete()
        messages.success(request, "Подкатегория удалена")
        return redirect("stock_category_detail", category_id=subcategory.category.id)

    return render(request, "inventory/warehouse/subcategories/confirm_delete.html", {
        "subcategory": subcategory,
        "has_items": has_items,
    })

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import CompanyForm
from .models import Company


@login_required(login_url='login')
def company_list(request):
    query = request.GET.get('q', '').strip()
    companies = Company.objects.all()
    if query:
        companies = companies.filter(
            Q(company_name__icontains=query) |
            Q(address__icontains=query) |
            Q(contact_person__icontains=query) |
            Q(email__icontains=query)
        )
    return render(request, 'companies/company_list.html', {'companies': companies, 'query': query})


@login_required(login_url='login')
def company_create(request):
    form = CompanyForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Company created successfully.')
        return redirect('companies:list')
    return render(request, 'companies/company_form.html', {'form': form, 'title': 'Add company'})


@login_required(login_url='login')
def company_update(request, pk):
    company = get_object_or_404(Company, pk=pk)
    form = CompanyForm(request.POST or None, request.FILES or None, instance=company)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Company updated successfully.')
        return redirect('companies:list')
    return render(request, 'companies/company_form.html', {
        'form': form,
        'title': 'Edit company',
        'company': company,
    })


@login_required(login_url='login')
@require_POST
def company_delete(request, pk):
    company = get_object_or_404(Company, pk=pk)
    company.delete()
    messages.success(request, 'Company deleted successfully.')
    return redirect('companies:list')

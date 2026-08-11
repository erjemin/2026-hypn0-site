from django.shortcuts import render
from django.http import HttpRequest, HttpResponse, Http404

# Create your views here.

def index(request: HttpRequest | None) -> HttpResponse:
    return render(request, 'index.html', {})


def tmp(request: HttpRequest | None) -> HttpResponse:
    return render(request, 'tmp.html', {})
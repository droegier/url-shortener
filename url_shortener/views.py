from django.core.urlresolvers import reverse
from django.shortcuts import render, get_object_or_404
from django.contrib import messages
from django.http import (HttpResponseRedirect,
                         Http404,
                         HttpResponsePermanentRedirect)

from .misc import (hash_encode,
                   get_absolute_short_url)
from .forms import URLShortenerForm
from .models import Link

# from basicauth.decorators import basic_auth_required

import base64
import logging

# @basic_auth_required
def index(request):
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    token_type, _, credentials = auth_header.partition(' ')
    logging.info('Credentials : ' + credentials)

    expected = base64.b64encode(b'admin:we<3lawyers').decode()
    logging.info('Expected : ' + expected)

    if token_type != 'Basic' or credentials != expected:
        logging.info('return 401')
        return HttpResponse(status=401)

    if request.method == 'POST':
        form = URLShortenerForm(request.POST)
        if form.is_valid():
            original_alias = form.cleaned_data['alias']
            alias = original_alias.lower()
            url = form.cleaned_data['url']
            new_link = Link(url=url)
            try:
                latest_link = Link.objects.latest('id')
                if Link.objects.filter(alias__exact=alias):
                    # handle alias conflict
                    new_link.alias = hash_encode(latest_link.id+1)
                    messages.add_message(request, messages.INFO,
                                         'Short URL {} already exists so a new short URL was created.'
                                         .format(get_absolute_short_url(request, original_alias)))
                    original_alias = new_link.alias
                else:
                    new_link.alias = alias or hash_encode(latest_link.id+1)
            except Link.DoesNotExist:
                new_link.alias = alias or hash_encode(1)
            new_link.save()
            return HttpResponseRedirect(reverse('url_shortener:preview', args=(original_alias or new_link.alias,)))
    else:
        form = URLShortenerForm()
    return render(request, 'url_shortener/index.html', {
        'form': form,
        'absolute_index_url': get_absolute_short_url(request, ''),
    })

# @basic_auth_required
def preview(request, alias):
    link = get_object_or_404(Link, alias__iexact=alias)
    return render(request, 'url_shortener/preview.html', {
        'alias': alias,
        'absolute_short_url': get_absolute_short_url(request, alias, remove_schema=False),
        'url': link.url,
    })


def redirect(request, alias, extra=''):
    link = get_object_or_404(Link, alias__iexact=alias)
    link.clicks_count += 1
    link.save()
    return HttpResponsePermanentRedirect(link.url + extra)

# @basic_auth_required
def analytics(request):
    links = list(Link.objects.all().order_by('-id'))
    if not links:
        return render(request, 'url_shortener/analytics.html')

    lim = 10
    try:
        page = int(request.GET['page'])
        if page <= 0:
            raise Http404("?page= parameter must be a valid positive integer")
    except KeyError:
        page = 1
    except ValueError:
        raise Http404('?page= parameter must be a valid positive integer')

    max_pages = len(links) // lim + bool(len(links) % lim)
    if page > max_pages:
        raise Http404('page ({}) is greater than max_pages ({})'.format(page, max_pages))

    if page == max_pages:
        # just get the remaining last items
        curr_links = links[-(len(links) % lim):]
    else:
        start = (page-1) * lim
        end = (page) * lim
        curr_links = links[start:end]
    return render(request, 'url_shortener/analytics.html', {
        'links': curr_links,
        'page': page,
        'max_pages': max_pages,
        'count_pages': ''.join(['x' for i in range(max_pages)]),  # HACK
    })

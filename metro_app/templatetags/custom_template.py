from django import template
from django.urls import reverse

register = template.Library()

@register.filter
def metro_to_user(object):
    if object == 'centroid':
        return 'zone'
    elif object == 'crossing':
        return 'intersection'
    elif object == 'link':
        return 'link'
    elif object == 'function':
        return 'congestion function'
    elif object == 'usertype':
        return 'traveler type'
    elif object == 'distribution':
        return 'distribution'
    return ''

@register.filter
def distribution_to_text(distribution, minutes=False):
    """Filter to output a Distribution object as text."""
    if minutes:
        # For tstar, convert the mean value to a string representing the time.
        hours = int(distribution.mean/60)
        minutes = int(distribution.mean % 60)
        if distribution.mean >= 780:
            hours -= 12
        elif distribution.mean < 60:
            hours += 12
        if minutes < 10:
            minutes = '0' + str(minutes)
        if distribution.mean < 720 or distribution.mean >= 1440:
            period = 'AM'
        else:
            period = 'PM'
        distribution.mean = '{0} ({1}:{2} {3})'.format(distribution.mean,
                                                       hours, minutes, period)
    string = ''
    if distribution.type == 'NONE': # Constant distribution.
        string += 'is equal to {}'.format(distribution.mean)
    elif distribution.type == 'UNIFORM':
        string += ('follows the uniform distribution of mean {0} and '
                   + 'standard-deviation {1}').format(distribution.mean,
                                                      distribution.std)
    elif distribution.type == 'NORMAL':
        string += ('follows the normal distribution with mean {0} and '
                   + 'standard-deviation {1}').format(distribution.mean,
                                                     distribution.std)
    elif distribution.type == 'LOGNORMAL':
        string += ('follows the log-normal distribution with mean {0} and '
                   + 'standard-deviation {1}').format(distribution.mean,
                                                     distribution.std)
    return string

@register.filter
def type_mu_to_text(choice):
    """Filter to output the type of a mu as text."""
    string = 'For each traveler, mu is '
    if choice == 'CONSTANT':
        string += '<strong>constant</strong>'
    elif choice == 'ALPHATI':
        string += '<strong>adaptive to the value of time</strong> in a car (α)'
    elif choice == 'MINTTCOST':
        string += '<strong>adaptive to the free flow travel cost</strong>'
    return string

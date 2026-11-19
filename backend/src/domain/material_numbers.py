"""Compact display of part numbers without altering their identities."""


def compact_part_numbers(numbers):
    result = []
    previous_prefix = None
    for number in numbers:
        prefix, separator, suffix = number.rpartition('-')
        if separator and prefix and suffix.isdecimal():
            result.append(suffix if prefix == previous_prefix else number)
            previous_prefix = prefix
        else:
            result.append(number)
            previous_prefix = None
    return '+'.join(result)

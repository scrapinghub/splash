# -*- coding: utf-8 -*-
import optparse

ONOFF = {True: "enabled", False: "disabled"}


def comma_separated_callback(*, is_valid_func=lambda v: True,
                             error_msg="{invalid} is not an allowed value"):
    """ Return an optparse callback for comma-separated args.
    Default value is not processed.

    Usage::

        my_callback = comma_separated_callback(
            is_valid_func=lambda v: v in {'foo', 'bar'},
            error_msg="{invalid} is not an allowed value for --option-name")

        op.add_option("--option-name",
            default=[],
            action='callback',
            type='string',
            callback=my_callback)

    """
    def callback(option, opt, value, parser):
        """ optparse callback for comma-separated args """
        values = value.split(',')
        for v in values:
            if not is_valid_func(v):
                msg = error_msg.format(value=value, invalid=v)
                raise optparse.OptionValueError(msg)
        setattr(parser.values, option.dest, values)
    return callback

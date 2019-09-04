============================================
 Simple PV simulation and network streaming
============================================

As a simple PV simulation test case, we provide two separate shell utilities, which might want to be packaged separately, but lets keep it simple.

Installation
------------
is handled by ``pipenv``.```

```shell
pipenv install --deploy
```

A [RabbitMQ](https://rabbitmq.com/) server -- to be used as broker -- is expected to run at AMQP_URL (defaulting to ```localhost:?```).

metersim
--------

``metersim`` connects to the broker and publishes the current demand (drawn from a Uniform distribution $\mathcal U([0, 60])$) and maybe a timestamp?

Usage
~~~~~

``metersim`` is available as an entrypoint. Run with ``metersim``.

pvsim
-----

``pvsim`` connects to the broker and subscribes to its demand topic for receiving real time (stamped?) electricity load measurements by the meter (it infinitely tries to re-establish the connection if it is interrupted (must be non-blocking)).

Each second it computes a simulated photovoltaic generation value.

``Time``, ``Meter``, ``PV`` and ``Residual load`` is written to a CSV file. With ``NaN``s for ``Meter`` and ``Residual load`` if the connection between ``meter`` and ``pvsim`` is interrupted.

Usage
~~~~~

``pvsim`` is available as an entrypoint, as well, and can be run with ``pvsim``.

.. note:: We might want to add a separate entrypoint or command line argument to ``pvsim`` for updating the shape parameter definition file (specifying different years, lat/lon coordinates) and/or switching to another one.

Model for photo voltaic generation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

is described in the documentation.

Licence
-------

Copyright (c) 2019 Jonas Hörsch

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

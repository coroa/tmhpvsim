============================================
 Simple PV simulation and network streaming
============================================

As a simple PV simulation test case, we provide two separate shell utilities, which might want to be packaged separately, but lets keep it simple.

Installation
------------
Can be handled by ``pipenv`` which takes care of installing the exact same versions, I tested the application with

.. code:: shell

    git clone https://github.com/coroa/tmhpvsim.git
    cd tmhpvsim
    pipenv install --deploy
    pipenv shell

But, instead, I would suggest to install manually with pip into a new venv:

.. code:: shell

    python3 -m venv tmhpvsim
    source tmhpvsim/bin/activate
    pip install https://github.com/coroa/tmhpvsim.git#egg=tmhpvsim


A `RabbitMQ <https://rabbitmq.com/>`_ server -- to be used as broker -- is expected to run at ``AMQP_URL`` (defaulting to ``localhost:5672``).

metersim
--------

``metersim`` connects to the broker and publishes the current demand (drawn from a Uniform distribution) and a timestamp.

Usage
~~~~~

.. code::

    Usage: metersim [OPTIONS]

    Options:
      --amqp-url TEXT             AMQP URL (defaults to 'amqp://localhost:5672/')
      --exchange TEXT             The name of the exchange (defaults to 'meter')
      -v, --verbose               Increase logging level from default WARN
      --realtime / --no-realtime  Switch off rate limiting (for simulation)
      --help                      Show this message and exit.


pvsim
-----

``pvsim`` connects to the broker and subscribes to its demand topic for receiving real time stamped electricity load measurements by the meter.

Each second it computes a simulated photovoltaic generation value.

``Time``, ``Meter``, ``PV`` and ``Residual load`` is written to a CSV file.

Usage
~~~~~

.. code::

    Usage: pvsim [OPTIONS] FILE

    Options:
      --amqp-url TEXT             AMQP URL (defaults to 'amqp://localhost:5672/')
      --exchange TEXT             The name of the exchange (defaults to 'meter')
      -v, --verbose               Increase logging level from default WARN
      --realtime / --no-realtime  Switch off rate limiting (for simulation)
      --help                      Show this message and exit.

.. note::  We might want to add a separate entrypoint or command line argument to ``pvsim`` for updating the shape parameter definition file (specifying different years, lat/lon coordinates) and/or switching to another one.

Model for photo voltaic generation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

is described in the documentation.

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

Instead, it is equally possible to install manually with pip into a new venv (in the subdirectory venv)

.. code:: shell

    git clone https://github.com/coroa/tmhpvsim.git
    cd tmhpvsim
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt

or use `pip` on directly on the remote repository, like

.. code:: shell

    python3 -m venv tmhpvsim
    source tmhpvsim/bin/activate
    pip install git+https://github.com/coroa/tmhpvsim.git#egg=tmhpvsim

but then you might not be using the pinned versions I tested the application with.

The installation registers two entrypoints, which are available as regular shell commands, `metersim` and `pvsim`. They are meant to be run from two separate shells or computers.
A `RabbitMQ <https://rabbitmq.com/>`_ server -- to be used as broker -- is expected to run at ``AMQP_URL`` (defaulting to ``localhost:5672``).

Both commands run according to their internal clock and produce simulated values for each second. If you supply the `--no-realtime` flag, the internal clock is not kept synchronized with local time, ie the commands run without any idle time.

The commands do not produce any output by default. Use `-v` or `-vv` to see more logging messages.

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

The FILE receives CSV data for all times for which a simulated PV value and a meter value arrived in `pvsim`. An examplary 6 second extract looks like:

=================== ================== ================== ================== 
time                meter              pv                 residual load      
=================== ================== ================== ================== 
2019-09-06 12:00:00 1374.0109643451744 165.172689783798   1208.8382745613765 
2019-09-06 12:00:01 5779.872039952913  157.28289673499341 5622.58914321792   
2019-09-06 12:00:02 2291.416886939385  169.98499896607225 2121.4318879733128 
2019-09-06 12:00:03 3899.7881213287983 161.48141720257405 3738.3067041262243 
2019-09-06 12:00:04 8399.970308135762  169.63913912237203 8230.33116901339   
2019-09-06 12:00:05 1718.7314214700184 173.56040563731491 1545.1710158327035 
=================== ================== ================== ================== 

Known problems
--------------
While `metersim` is able to ride through a dropped connection from RabbitMQ (like a restart), `pvsim` on the other hand will swallow the Exception which signals the connection drop, due to a limitation in the underlying `aio-pika<https://aio-pika.readthedocs.io/en/latest/>` library. Refer to `aio-pika#230<https://github.com/mosquito/aio-pika/issues/230>`.

In an ideal world one would rewrite both scripts using its stable backend library `aiormq<https://github.com/mosquito/aiormq>`.

Installation
============

This page will go over the installation process of magmatic and Lavalink.
After installing, see [placeholder] for instructions on getting started with using magmatic.

Installing magmatic
-------------------

Magmatic is a standard Python package. You can install it using **pip**.

You must have **Python 3.8** or higher in order to use magmatic.

Standard installation (PyPI)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The following will install the latest **stable** version of magmatic.
This is recommended.

.. tab:: Windows

    .. code:: bash

        py -3 -m pip install -U magmatic

    In a `virtual environment <https://docs.python.org/3/library/venv.html>`_:

    .. code:: bash

        # Given "venv" is the name of your venv directory:
        venv/Scripts/activate
        pip install -U magmatic

.. tab:: Linux

    .. code:: bash

        python3 -m pip install -U magmatic

    In a `virtual environment <https://docs.python.org/3/library/venv.html>`_:

    .. code:: bash

        # Given "venv" is the name of your venv directory:
        source venv/bin/activate
        pip install -U magmatic

GitHub installation
~~~~~~~~~~~~~~~~~~~

You may also install from GitHub if you wish. You must have Git installed in order to do this.

Note that installing from GitHub will likely install an unstable version of magmatic.
Install using the standard method above if you with to use the stable version.

The following installs magmatic from GitHub:

.. tab:: Windows

    .. code:: bash

        py -3 -m pip install -U git+https://github.com/jay3332/magmatic

    In a `virtual environment <https://docs.python.org/3/library/venv.html>`_:

    .. code:: bash

        # Given "venv" is the name of your venv directory:
        venv/Scripts/activate
        pip install -U git+https://github.com/jay3332/magmatic

.. tab:: Linux

    .. code:: bash

        python3 -m pip install -U git+https://github.com/jay3332/magmatic

    In a `virtual environment <https://docs.python.org/3/library/venv.html>`_:

    .. code:: bash

        # Given "venv" is the name of your venv directory:
        source venv/bin/activate
        pip install -U git+https://github.com/jay3332/magmatic

Setting up Lavalink
-------------------

Magmatic is a wrapper around Lavalink. An instance of Lavalink must be running
and provided for magmatic in order for it to function.

Installing Lavalink
~~~~~~~~~~~~~~~~~~~

Work in progress, check back later.

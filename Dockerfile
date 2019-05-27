# This install is for ubuntu 18.04 and python 3.6
FROM ubuntu:18.04

# Update
RUN apt-get -y update

# Install python/pip
RUN apt-get -y install python3 && \
    apt-get -y install python3-pip

# Install git
RUN apt-get -y install git

# Clone repo and remove unneeded files
RUN mkdir /extra && \
    cd /extra && \
    git clone https://github.com/justinblaber/multi_pyspin.git && \
    cd multi_pyspin && \
    rm BFS-U3-32S4_1804.0.113.3.zip && \
    rm Dockerfile && \
    rm README.md && \
    rm Singularity && \
    rm Singularity.1.0.0 && \
    rm *.yaml

# Install multi_pyspin
RUN cd /extra/multi_pyspin && \
    tar xvfz spinnaker-1.21.0.61-amd64-Ubuntu18.04-pkg.tar.gz && \
    cd spinnaker-1.21.0.61-amd64 && \
    apt-get -y install sudo && \
    apt-get -y install libusb-1.0-0 && \
    printf 'y\nn\n' | sh install_spinnaker.sh && \
    cd ../ && \
    rm -rf spinnaker-1.21.0.61-amd64 && \
    python3 -m pip install -r requirements.txt && \
    rm spinnaker_python-1.21.0.61-cp36-cp36m-linux_x86_64.whl

# Set environment
ENV PATH "$PATH":/extra/multi_pyspin
ENV PYTHONPATH /extra/multi_pyspin

# Start GUI
CMD python3 multi_pyspin_gui.py

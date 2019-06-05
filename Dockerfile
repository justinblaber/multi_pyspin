# This install is for ubuntu 18.04 and python 3.6
FROM ubuntu:18.04

# Disable interactive dialogue with dpkg
ENV DEBIAN_FRONTEND noninteractive

# Disable python user site
ENV PYTHONNOUSERSITE 1

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
    rm Singularity* && \
    rm *.yaml

# Install multi_pyspin
RUN cd /extra/multi_pyspin && \
    tar xvfz spinnaker-1.23.0.27-amd64-Ubuntu18.04-pkg.tar.gz && \
    cd spinnaker-1.23.0.27-amd64 && \
    apt-get -y install sudo && \
    apt-get -y install libusb-1.0-0 && \
    printf 'y\nn\n' | sh install_spinnaker.sh && \
    cd ../ && \
    rm -rf spinnaker-1.23.0.27-amd64 && \
    rm spinnaker-1.23.0.27-amd64-Ubuntu18.04-pkg.tar.gz && \
    python3 -m pip install -r requirements.txt && \
    rm requirements.txt && \
    rm spinnaker_python-1.23.0.27-cp36-cp36m-linux_x86_64.whl && \
    apt-get -y install python3-tk && \
    apt-get -y install libswscale4 && \
    apt-get -y install libavcodec57 && \
    apt-get -y install libavformat57

# Set environment
ENV PYTHONPATH /extra/multi_pyspin

# Start GUI
CMD python3 /extra/multi_pyspin/multi_pyspin_gui.py

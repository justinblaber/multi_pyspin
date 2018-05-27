# This install is for ubuntu 16.04 and python 3.5
FROM ubuntu:16.04

# Update
RUN apt-get -y update && apt-get -y upgrade

# Install python/pip
RUN apt-get -y install python3 && \
    apt-get -y install python3-pip && \
    ln -s /usr/bin/python3 /usr/bin/python

# Install stereo_pyspin
RUN mkdir /extra && \
    cd /extra && \
    apt-get -y install sudo && \
    apt-get -y install git && \
    git clone https://github.com/justinblaber/stereo_pyspin.git && \
    cd stereo_pyspin && \
    tar xvfz spinnaker-1.10.0.31-amd64.tar.gz && \
    cd spinnaker-1.10.0.31-amd64 && \
    apt-get -y install libavcodec-ffmpeg56 && \
    apt-get -y install libavformat-ffmpeg56 && \
    apt-get -y install libswscale-ffmpeg3 && \
    apt-get -y install libswresample-ffmpeg1 && \
    apt-get -y install libavutil-ffmpeg54 && \
    apt-get -y install libusb-1.0-0 && \
    printf 'y\nn\n' | sh install_spinnaker.sh && \
    cd ../ && \
    rm -rf spinnaker-1.10.0.31-amd64 && \
    python -m pip install --upgrade pip && \
    python -m pip install -r requirements.txt && \
    apt-get -y install python3-tk

ENV PATH "$PATH":/extra/stereo_pyspin
ENV PYTHONPATH /extra/stereo_pyspin

CMD stereo_pyspin_gui

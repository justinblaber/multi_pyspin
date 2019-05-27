# multi_pyspin
A simple multi camera library using PySpin.

# Installation and User Guide (Spinnaker USB cameras on Linux)

1) Increase USB file system memory. In this case, I've set it to 16gb (16000 mb). Please update the number to whatever you think is appropriate for your machine. There are two ways:

   #### Permanent way:

   1. Open the `/etc/default/grub` file in any text editor. Find and replace:
    
      `GRUB_CMDLINE_LINUX_DEFAULT="quiet splash"`
    
      with this:
   
      `GRUB_CMDLINE_LINUX_DEFAULT="quiet splash usbcore.usbfs_memory_mb=16000"`

   2. Update grub with these settings:

      `$ sudo update-grub`

   3. Reboot and test a USB camera.

   #### Temporary way:

   1. Run the following command:

      `sudo sh -c 'echo 16000 > /sys/module/usbcore/parameters/usbfs_memory_mb'`

2) After doing either the permanent or temporary way, confirm that you have successfully updated the memory limit by running the following command:

   `cat /sys/module/usbcore/parameters/usbfs_memory_mb`
   
   The output should be 16000.
   
3) Configure udev rules to allow access to USB devices:
   
   ```
   cd /tmp
   wget https://github.com/justinblaber/multi_pyspin/blob/master/spinnaker-1.21.0.61-amd64-Ubuntu18.04-pkg.tar.gz?raw=true -O spinnaker-1.21.0.61-amd64-Ubuntu18.04-pkg.tar.gz
   tar xvfz spinnaker-1.21.0.61-amd64-Ubuntu18.04-pkg.tar.gz
   cd spinnaker-1.21.0.61-amd64
   sudo sh spin-conf
   ```

4) [Install singularity](https://singularity.lbl.gov/install-linux)

5) Download singularity image:

   ```
   mkdir -p ~/multi_pyspin
   cd ~/multi_pyspin
   singularity pull --name multi_pyspin.simg shub://justinblaber/multi_pyspin
   ```
 
6) Run the singularity image:

   `~/multi_pyspin/multi_pyspin.simg`
   
   A gui should appear like so:

   ![alt text](https://i.imgur.com/0XrLia4.png)
   
7) Find and initialize both primary and secondary cameras, then start the stream. If successful, the gui should look like:

   ![alt text](https://i.imgur.com/16Njddo.png)
   
8) After the stream is started, you can save images:

   `16276941_2018-07-10_02:04:23_916915_1_L.png`:
    ![alt text](https://i.imgur.com/6IbZG1K.jpg)
    
   `16276942_2018-07-10_02:04:23_918101_1_R.png`:
    ![alt text](https://i.imgur.com/zCkXFhz.jpg)
    
   It's important to note that the images should be acquired very closely in time (especially if a hardware trigger is used). 

   

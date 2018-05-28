# stereo_pyspin
A simple stereo camera library using PySpin.

# Installation and User Guide (Spinnaker USB cameras on Linux)

1) Increase USB file system memory. There are two ways:

   #### Permanent way:

   1. Open the `/etc/default/grub` file in any text editor. Find and replace:
    
      `GRUB_CMDLINE_LINUX_DEFAULT="quiet splash"`
    
      with this:
   
      `GRUB_CMDLINE_LINUX_DEFAULT="quiet splash usbcore.usbfs_memory_mb=1000"`

   2. Update grub with these settings:

      `$ sudo update-grub`

   3. Reboot and test a USB camera.

   #### Temporary way:

   1. Run the following command:

      `sudo sh -c 'echo 1000 > /sys/module/usbcore/parameters/usbfs_memory_mb'`

2) After doing either the permanent or temporary way, confirm that you have successfully updated the memory limit by running the following command:

   `cat /sys/module/usbcore/parameters/usbfs_memory_mb`
   
   The output should be 1000.
   
3) Configure udev rules to allow access to USB devices:
   
   ```
   cd /tmp
   wget https://github.com/justinblaber/stereo_pyspin/blob/master/spinnaker-1.10.0.31-amd64.tar.gz?raw=true -O spinnaker-1.10.0.31-amd64.tar.gz
   tar xvfz spinnaker-1.10.0.31-amd64.tar.gz
   sudo sh spinnaker-1.10.0.31-amd64/spin-conf
   ```

4) [Install singularity](https://singularity.lbl.gov/install-linux)

5) Download singularity image:

   ```
   mkdir -p ~/stereo_pyspin
   cd ~/stereo_pyspin
   singularity pull --name stereo_pyspin.img shub://justinblaber/stereo_pyspin
   ```

6) Set up acquisition folder and copy YAML configurations for each camera into it:

   ```
   mkdir -p ~/Desktop/stereo_pyspin_test
   cd ~/Desktop/stereo_pyspin_test
   wget https://raw.githubusercontent.com/justinblaber/stereo_pyspin/master/primary.yaml
   wget https://raw.githubusercontent.com/justinblaber/stereo_pyspin/master/secondary.yaml
   ```
   
   Make sure to modify primary.yaml and secondary.yaml to set the serial numbers and do the appropriate camera initializations.
   
7) Run the singularity image:

   `singularity run ~/stereo_pyspin/stereo_pyspin.img`
   
   A gui should appear like so:

   ![alt text](https://i.imgur.com/7G2QBhH.png)
   
8) Find and initialize both primary and secondary cameras, then start the stream. If successful, the gui should look like:

   ![alt text](https://i.imgur.com/hamwPeE.png)
   
9) After the stream is started, you can save images:

   16276941_2018-05-28_00:13:27_877002_1_L.png:
    ![alt text](https://i.imgur.com/6F49APZ.jpg)
    
   16276942_2018-05-28_00:13:27_877956_1_R.png 
    ![alt text](https://i.imgur.com/mbcDm3l.jpg)
    
   It's important to note that the images should be acquired very closely in time (especially if a hardware trigger is used). 

   

#!/bin/bash
# Script to prepare an OpenSUSE Tumbleweed VM template with cloud-init support

set -e

# Configuration
TEMPLATE_NAME="opensuse-tumbleweed-template"
TEMPLATE_DIR="/var/lib/libvirt/images"
OUTPUT_PATH="${TEMPLATE_DIR}/${TEMPLATE_NAME}.qcow2"
ISO_URL="https://download.opensuse.org/tumbleweed/iso/openSUSE-Tumbleweed-NET-x86_64-Current.iso"
ISO_PATH="${TEMPLATE_DIR}/opensuse-tumbleweed.iso"
VM_SIZE="20G"
VM_MEMORY="2048"
VM_CPUS="2"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}This script must be run as root${NC}"
  exit 1
fi

echo -e "${GREEN}=== OpenSUSE Tumbleweed Template VM Preparation ===${NC}"

# Create directories
mkdir -p "${TEMPLATE_DIR}"

# Download OpenSUSE Tumbleweed ISO if needed
if [ ! -f "${ISO_PATH}" ]; then
    echo -e "${YELLOW}Downloading OpenSUSE Tumbleweed ISO...${NC}"
    curl -L -o "${ISO_PATH}" "${ISO_URL}"
    echo -e "${GREEN}Download complete!${NC}"
fi

# Create the base disk image
if [ ! -f "${OUTPUT_PATH}" ]; then
    echo -e "${YELLOW}Creating base disk image...${NC}"
    qemu-img create -f qcow2 "${OUTPUT_PATH}" "${VM_SIZE}"
    echo -e "${GREEN}Base disk image created!${NC}"
else
    echo -e "${YELLOW}Base disk image already exists, skipping creation.${NC}"
    read -p "Do you want to override the existing image? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Creating new base disk image...${NC}"
        qemu-img create -f qcow2 "${OUTPUT_PATH}" "${VM_SIZE}"
        echo -e "${GREEN}Base disk image created!${NC}"
    fi
fi

# Create autoinstall ISO
echo -e "${YELLOW}Creating autoinstallation content...${NC}"

# Create a temporary directory for autoinstall content
TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT

# Create AutoYaST XML configuration
cat > "${TEMP_DIR}/autoinst.xml" << 'EOF'
<?xml version="1.0"?>
<!DOCTYPE profile>
<profile xmlns="http://www.suse.com/1.0/yast2ns" xmlns:config="http://www.suse.com/1.0/configns">
  <general>
    <mode>
      <confirm config:type="boolean">false</confirm>
      <final_reboot config:type="boolean">true</final_reboot>
    </mode>
  </general>
  <keyboard>
    <keymap>english-us</keymap>
  </keyboard>
  <language>
    <language>en_US</language>
  </language>
  <timezone>
    <timezone>UTC</timezone>
    <hwclock>UTC</hwclock>
  </timezone>
  <networking>
    <dhcp_options>
      <dhclient_client_id/>
      <dhclient_hostname_option>AUTO</dhclient_hostname_option>
    </dhcp_options>
    <keep_install_network config:type="boolean">true</keep_install_network>
    <setup_before_proposal config:type="boolean">true</setup_before_proposal>
    <start_immediately config:type="boolean">true</start_immediately>
  </networking>
  <bootloader>
    <loader_type>grub2</loader_type>
  </bootloader>
  <partitioning config:type="list">
    <drive>
      <use>all</use>
      <partitions config:type="list">
        <partition>
          <mount>/</mount>
          <size>max</size>
        </partition>
        <partition>
          <mount>swap</mount>
          <size>2G</size>
        </partition>
      </partitions>
    </drive>
  </partitioning>
  <software>
    <products config:type="list">
      <product>openSUSE</product>
    </products>
    <install_recommended config:type="boolean">true</install_recommended>
    <packages config:type="list">
      <package>qemu-guest-agent</package>
      <package>cloud-init</package>
      <package>openssh</package>
      <package>sudo</package>
      <package>vim</package>
      <package>curl</package>
      <package>wget</package>
    </packages>
    <patterns config:type="list">
      <pattern>minimal_base</pattern>
    </patterns>
  </software>
  <users config:type="list">
    <user>
      <username>root</username>
      <user_password>linux</user_password>
      <encrypted config:type="boolean">false</encrypted>
    </user>
    <user>
      <username>agent</username>
      <user_password>agent</user_password>
      <encrypted config:type="boolean">false</encrypted>
      <authorized_keys config:type="list">
        <!-- Add your SSH public key here if needed -->
      </authorized_keys>
    </user>
  </users>
  <groups config:type="list">
    <group>
      <groupname>sudo</groupname>
      <userlist>agent</userlist>
    </group>
  </groups>
  <scripts>
    <chroot-scripts config:type="list">
      <script>
        <chrooted config:type="boolean">true</chrooted>
        <filename>enable_services.sh</filename>
        <interpreter>shell</interpreter>
        <source><![CDATA[
#!/bin/sh
# Enable services
systemctl enable sshd
systemctl enable qemu-guest-agent
systemctl enable cloud-init

# Configure sudo for agent user
echo "agent ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/agent
chmod 440 /etc/sudoers.d/agent

# Configure cloud-init
cat > /etc/cloud/cloud.cfg.d/99_opensuse.cfg << 'CLOUDCFG'
datasource_list: [ NoCloud, OpenStack, None ]
disable_root: false
ssh_pwauth: true
CLOUDCFG

# Clean up
rm -f /etc/machine-id
rm -f /var/lib/dbus/machine-id
touch /etc/machine-id
        ]]></source>
      </script>
    </chroot-scripts>
  </scripts>
</profile>
EOF

# Create ISO with AutoYaST configuration
AUTOINSTALL_ISO="/tmp/autoinstall.iso"
#genisoimage -output "${AUTOINSTALL_ISO}" -volid "OEMDRV" -rational-rock "${TEMP_DIR}/autoinst.xml"
mkisofs -output "${AUTOINSTALL_ISO}" -volid "OEMDRV" -rational-rock "${TEMP_DIR}/autoinst.xml"

echo -e "${GREEN}AutoYaST configuration created!${NC}"

# Create and start the VM for installation
echo -e "${YELLOW}Creating installation VM...${NC}"
virt-install \
  --name temp-template-install \
  --memory ${VM_MEMORY} \
  --vcpus ${VM_CPUS} \
  --disk path=${OUTPUT_PATH},format=qcow2 \
  --disk path=${AUTOINSTALL_ISO},device=cdrom \
  --location ${ISO_PATH} \
  --os-variant=opensusetumbleweed \
  --network default \
  --graphics vnc,listen=0.0.0.0 \
  --noautoconsole \
  --extra-args="autoyast=device:sr0:/autoinst.xml"

echo -e "${GREEN}Installation started!${NC}"
echo -e "${YELLOW}Waiting for installation to complete...${NC}"
echo -e "You can monitor the installation using: virt-viewer temp-template-install"

# Wait for installation to complete (VM will shut down when done)
while virsh domstate temp-template-install | grep -q running; do
    echo -n "."
    sleep 10
done

echo -e "\n${GREEN}Installation complete!${NC}"

# Clean up
echo -e "${YELLOW}Cleaning up...${NC}"
virsh undefine temp-template-install
rm -f "${AUTOINSTALL_ISO}"

# Prepare the template for cloud-init (sysprep)
echo -e "${YELLOW}Preparing template for cloud-init...${NC}"
virt-sysprep -a "${OUTPUT_PATH}" \
  --operations defaults,-ssh-hostkeys,-ssh-userdir,-tmp-files,-customize \
  --hostname template-vm

echo -e "${GREEN}=== Template VM creation complete! ===${NC}"
echo -e "Template path: ${OUTPUT_PATH}"
echo -e "Use this template with the VM Manager to create new VMs."
echo -e "Default credentials: agent / agent"

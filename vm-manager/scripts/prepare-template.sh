#!/bin/bash
# Script to prepare an OpenSUSE Tumbleweed VM template

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="${SCRIPT_DIR}/.."
TEMPLATE_DIR="${BASE_DIR}/data/templates"
TEMPLATE_NAME="opensuse-tumbleweed.qcow2"
TEMPLATE_PATH="${TEMPLATE_DIR}/${TEMPLATE_NAME}"
SSH_KEY_PATH="${BASE_DIR}/data/ssh/agent_key"
ISO_URL="https://download.opensuse.org/tumbleweed/iso/openSUSE-Tumbleweed-NET-x86_64-Current.iso"
ISO_PATH="${TEMPLATE_DIR}/opensuse-tumbleweed.iso"

# Create directories
mkdir -p "${TEMPLATE_DIR}"

echo "=== Preparing OpenSUSE Tumbleweed VM Template ==="

# Download OpenSUSE Tumbleweed ISO if not exists
if [ ! -f "${ISO_PATH}" ]; then
    echo "Downloading OpenSUSE Tumbleweed ISO..."
    curl -L -o "${ISO_PATH}" "${ISO_URL}"
fi

# Create SSH key if not exists
if [ ! -f "${SSH_KEY_PATH}" ]; then
    echo "Creating SSH key for agent user..."
    mkdir -p "$(dirname "${SSH_KEY_PATH}")"
    ssh-keygen -t rsa -b 4096 -f "${SSH_KEY_PATH}" -N "" -C "agent@linux-agent-system"
fi

# Create template disk if not exists
if [ ! -f "${TEMPLATE_PATH}" ]; then
    echo "Creating template disk..."
    qemu-img create -f qcow2 "${TEMPLATE_PATH}" 20G
    
    echo "Template disk created. Now you need to install OpenSUSE Tumbleweed."
    echo "Recommended approach:"
    echo "1. Use virt-manager to create a new VM using the template disk"
    echo "2. Install OpenSUSE Tumbleweed with minimal configuration"
    echo "3. Create an 'agent' user with sudo privileges"
    echo "4. Set up SSH access for the agent user"
    echo "5. Install required packages: qemu-guest-agent, cloud-init"
    echo "6. Shutdown the VM and the template is ready to use"
    
    echo "Alternatively, use virt-install command:"
    echo "virt-install --name opensuse-template --memory 2048 --vcpus 2 \\"
    echo "  --disk path=${TEMPLATE_PATH},format=qcow2 \\"
    echo "  --cdrom ${ISO_PATH} \\"
    echo "  --os-variant opensuse-tumbleweed \\"
    echo "  --network default \\"
    echo "  --graphics vnc,listen=0.0.0.0"
else
    echo "Template disk already exists at: ${TEMPLATE_PATH}"
fi

echo "=== Template Preparation Complete ==="
echo "Template path: ${TEMPLATE_PATH}"
echo "SSH key path: ${SSH_KEY_PATH}"

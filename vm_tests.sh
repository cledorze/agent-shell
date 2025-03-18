#!/bin/bash
# Script pour tester les fonctionnalités VM

echo "Test de création de VM avec libvirt"

echo "1. Vérification des permissions et services"
echo "-------------------------------------------"
echo "Utilisateur actuel: $(whoami)"
echo "Groupes: $(groups)"
echo "Service libvirtd: $(systemctl is-active libvirtd)"
echo "Socket libvirt: $(ls -la /var/run/libvirt/libvirt-sock)"

echo
echo "2. Test de commandes libvirt de base"
echo "-----------------------------------"
echo "Version virsh: $(virsh --version)"
echo 
echo "Liste des VMs:"
virsh list --all
echo
echo "Liste des réseaux:"
virsh net-list --all
echo
echo "Liste des pools de stockage:"
virsh pool-list --all

echo
echo "3. Test de création d'une VM de test"
echo "-----------------------------------"
# Créer un disque basé sur le template
VM_NAME="test-vm-$(date +%s)"
DISK_PATH="/var/lib/libvirt/images/${VM_NAME}.qcow2"
TEMPLATE="/var/lib/libvirt/images/templates/opensuse-tumbleweed.qcow2"

if [ ! -f "$TEMPLATE" ]; then
    echo "⚠️ Template d'image introuvable à $TEMPLATE"
    echo "Création d'une image vide à la place"
    qemu-img create -f qcow2 "$DISK_PATH" 10G
else
    echo "Création d'un disque basé sur le template..."
    qemu-img create -f qcow2 -b "$TEMPLATE" "$DISK_PATH"
fi

echo "Définition de la VM..."
cat > /tmp/${VM_NAME}.xml << EOF
<domain type='kvm'>
  <name>${VM_NAME}</name>
  <memory unit='GiB'>2</memory>
  <vcpu>1</vcpu>
  <os>
    <type arch='x86_64'>hvm</type>
    <boot dev='hd'/>
  </os>
  <features>
    <acpi/>
    <apic/>
  </features>
  <devices>
    <disk type='file' device='disk'>
      <driver name='qemu' type='qcow2'/>
      <source file='${DISK_PATH}'/>
      <target dev='vda' bus='virtio'/>
    </disk>
    <interface type='network'>
      <source network='default'/>
      <model type='virtio'/>
    </interface>
    <console type='pty'/>
    <graphics type='vnc' port='-1' autoport='yes' listen='0.0.0.0'/>
  </devices>
</domain>
EOF

echo "Essai de définition et démarrage de la VM..."
if virsh define /tmp/${VM_NAME}.xml; then
    echo "✅ VM définie avec succès"
    
    if virsh start ${VM_NAME}; then
        echo "✅ VM démarrée avec succès"
    else
        echo "❌ Échec du démarrage de la VM"
    fi
    
    echo "État de la VM:"
    virsh dominfo ${VM_NAME}
    
    echo "Suppression de la VM de test..."
    virsh destroy ${VM_NAME} 2>/dev/null
    virsh undefine ${VM_NAME}
    rm -f "$DISK_PATH"
else
    echo "❌ Échec de définition de la VM"
fi

rm -f /tmp/${VM_NAME}.xml

echo
echo "Tests de libvirt terminés"
echo "Si les tests ont échoué, exécutez le script setup-libvirt.sh en tant que root"

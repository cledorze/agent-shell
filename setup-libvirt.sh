#!/bin/bash
# Script pour configurer libvirt et préparer l'environnement pour la création de VMs

set -e

echo "Configuration de l'environnement pour la création de VMs réelles avec libvirt"

# Vérifier si on est root
if [ "$(id -u)" -ne 0 ]; then
    echo "Ce script doit être exécuté en tant que root ou avec sudo"
    exit 1
fi

# Installer les paquets nécessaires
echo "Installation des paquets nécessaires..."
if command -v apt-get &>/dev/null; then
    apt-get update
    apt-get install -y qemu-kvm libvirt-daemon-system virtinst bridge-utils libvirt-clients
elif command -v dnf &>/dev/null; then
    dnf install -y qemu-kvm libvirt virt-install bridge-utils libvirt-client
elif command -v zypper &>/dev/null; then
    zypper install -y qemu-kvm libvirt virt-install bridge-utils libvirt-client
else
    echo "Système d'exploitation non supporté. Veuillez installer manuellement libvirt."
    exit 1
fi

# Démarrer et activer libvirtd
echo "Démarrage du service libvirtd..."
systemctl enable libvirtd
systemctl start libvirtd

# Ajouter l'utilisateur courant aux groupes nécessaires
echo "Ajout de l'utilisateur aux groupes libvirt et kvm..."
CURRENT_USER=${SUDO_USER:-$(whoami)}
usermod -aG libvirt "$CURRENT_USER"
usermod -aG kvm "$CURRENT_USER"

# Créer les répertoires pour les templates de VM
echo "Création des répertoires pour les templates..."
mkdir -p /var/lib/libvirt/images/templates

# Télécharger l'image OpenSUSE Tumbleweed si elle n'existe pas
OPENSUSE_IMAGE="/var/lib/libvirt/images/templates/opensuse-tumbleweed.qcow2"
if [ ! -f "$OPENSUSE_IMAGE" ]; then
    echo "Téléchargement de l'image OpenSUSE Tumbleweed..."
    wget https://download.opensuse.org/tumbleweed/appliances/openSUSE-Tumbleweed-JeOS.x86_64-kvm-and-xen.qcow2 -O "$OPENSUSE_IMAGE"
    # Alternativement, vous pouvez utiliser une image plus légère comme:
    # wget https://download.opensuse.org/repositories/Cloud:/Images:/Tumbleweed/images/openSUSE-Tumbleweed-JeOS.x86_64-OpenStack-Cloud.qcow2 -O "$OPENSUSE_IMAGE"
fi

# Définir les permissions correctes
echo "Configuration des permissions..."
chmod 644 "$OPENSUSE_IMAGE"
chmod 666 /var/run/libvirt/libvirt-sock

# Créer le réseau par défaut si nécessaire
if ! virsh net-info default &>/dev/null; then
    echo "Création du réseau par défaut..."
    virsh net-define /etc/libvirt/qemu/networks/default.xml
    virsh net-start default
    virsh net-autostart default
fi

echo "Vérification de la configuration..."
echo "1. Test de la connexion libvirt:"
if virsh version; then
    echo "✅ Connexion à libvirt réussie"
else
    echo "❌ Échec de connexion à libvirt"
fi

echo "2. Vérification de l'image template:"
if [ -f "$OPENSUSE_IMAGE" ]; then
    echo "✅ Image template trouvée"
else
    echo "❌ Image template manquante"
fi

echo "3. Vérification du réseau par défaut:"
if virsh net-info default | grep -q "Active:.*yes"; then
    echo "✅ Réseau par défaut actif"
else
    echo "❌ Réseau par défaut inactif"
fi

echo ""
echo "Configuration terminée. Veuillez redémarrer votre session pour que les changements de groupe prennent effet."
echo "Ensuite, lancez le système avec 'sudo podman-compose -f docker-compose.python.yml up -d'"

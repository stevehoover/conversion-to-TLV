#!/bin/bash

# Exit on error
set -e

echo "🚀 Starting installation of dependencies for Verilog to TL-Verilog conversion project..."

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to install system dependencies
install_system_deps() {
    echo "📦 Installing system dependencies..."
    if command_exists apt-get; then
        sudo apt-get update
        sudo apt-get install -y \
            build-essential \
            git \
            python3 \
            python3-pip \
            cmake \
            bison \
            flex \
            libreadline-dev \
            gawk \
            tcl-dev \
            libffi-dev \
            graphviz \
            xdot \
            pkg-config \
            python3-dev
    elif command_exists brew; then
        brew install \
            cmake \
            bison \
            flex \
            readline \
            graphviz \
            pkg-config
    else
        echo "❌ Unsupported package manager. Please install dependencies manually."
        exit 1
    fi
}

# Function to install Python dependencies
install_python_deps() {
    echo "🐍 Installing Python dependencies..."
    pip3 install --upgrade pip
    pip3 install pynput openai
}

# Function to install Yosys
install_yosys() {
    echo "🔧 Installing Yosys..."
    
    # Remove existing Yosys if installed via package manager
    if command_exists yosys; then
        echo "📦 Removing existing Yosys package..."
        sudo apt-get remove -y yosys
    fi

    # Clean up existing yosys directory if it exists
    if [ -d "yosys" ]; then
        echo "🧹 Cleaning up existing yosys directory..."
        rm -rf yosys
    fi

    echo "🔧 Building Yosys from source..."
    git clone https://github.com/YosysHQ/yosys.git
    cd yosys
    make config-gcc
    make
    sudo make install
    cd ..
}

# Function to install SymbiYosys
install_sby() {
    echo "🔧 Installing SymbiYosys..."
    if command_exists sby; then
        echo "✅ SymbiYosys is already installed"
        return
    fi

    git clone https://github.com/YosysHQ/SymbiYosys.git
    cd SymbiYosys
    make
    sudo make install
    cd ..
}

# Function to install EQY
install_eqy() {
    echo "🔧 Installing EQY..."
    if command_exists eqy; then
        echo "✅ EQY is already installed"
        return
    fi

    # Ensure Yosys is properly configured
    if ! command_exists yosys-config; then
        echo "❌ yosys-config not found. Reinstalling Yosys..."
        install_yosys
    fi

    # Clean up existing eqy directory if it exists
    if [ -d "eqy" ]; then
        echo "🧹 Cleaning up existing eqy directory..."
        rm -rf eqy
    fi

    git clone https://github.com/YosysHQ/eqy.git
    cd eqy
    make
    sudo make install
    cd ..
}

# Main installation process
echo "🔍 Checking system requirements..."
install_system_deps

echo "📦 Installing Python packages..."
install_python_deps

echo "🔧 Installing EDA tools..."
install_yosys
install_sby
install_eqy

echo "✨ Installation complete! Here's what was installed:"
echo "✅ System dependencies"
echo "✅ Python packages (pynput, openai)"
echo "✅ Yosys"
echo "✅ SymbiYosys"
echo "✅ EQY"

echo "
🎉 All dependencies have been installed successfully!
To verify the installation, you can run:
yosys --version
sby --version
eqy --version
"

# Verify installations
echo "🔍 Verifying installations..."
yosys --version || echo "❌ Yosys installation might have issues"
sby --version || echo "❌ SymbiYosys installation might have issues"
eqy --version || echo "❌ EQY installation might have issues" 
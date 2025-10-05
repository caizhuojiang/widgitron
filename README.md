# Widgitron

<img src="icons/widgitron.png" alt="Widgitron Logo" width="150">

**A modular desktop widget framework for researchers and developers**

Build AI-powered dashboards and monitoring tools with Python and PyQt5. Create beautiful, floating desktop widgets that are always accessible.

![Version](https://img.shields.io/badge/version-0.1.0-blue)
![Python](https://img.shields.io/badge/python-3.7+-green)
![License](https://img.shields.io/badge/license-MIT-orange)


## 🗺️ Roadmap

### ✅ Completed
- [x] Main framework setup
- [x] GPU monitor widget

### 🚧 Planned
- [ ] Paper deadline widget
- [ ] Paper monitoring update widget
- [ ] More GPU monitor widget styles
- [ ] Server file management widget
- [ ] More widgets
- [ ] Plugin system for third-party widgets
- [ ] Widget themes and styles
- [ ] Multi-monitor support improvements


## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/caizhuojiang/widgitron.git
cd widgitron

# Install dependencies
pip install -r requirements.txt
```

### Configuration

**Configure GPU Monitor** (`configs/gpu_monitor.json`):
```json
{
    "servers": [
        {
            "host": "your-server.com",
            "user": "username",
            "key_file": "~/.ssh/id_rsa",
            "port": 22
        }
    ],
    "update_interval": 1
}
```

See `configs/gpu_monitor.example.json` for more options.

### Run

```bash
python widgitron.py
```

## 📊 Built-in Widgets

### GPU Monitor

Monitor GPU usage on multiple remote servers:
- 📡 SSH connection support
- 🔄 Real-time updates
- 🔔 Idle notifications
- 🌐 Proxy/jump host support
- 💾 Memory usage tracking
- ⚡ Utilization percentage

## 🤝 Contributing

Contributions welcome! Here's how:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-widget`)
3. Commit your changes (`git commit -m 'Add amazing widget'`)
4. Push to the branch (`git push origin feature/amazing-widget`)
5. Open a Pull Request

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

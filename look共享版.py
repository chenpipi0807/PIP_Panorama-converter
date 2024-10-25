import gradio as gr
import os
import subprocess
from PIL import Image
import shutil
import webbrowser
import http.server
import socketserver
import threading
import json
from datetime import datetime
import socket

# 在文件开头添加
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")

# 设置输出目录
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# HTML模板中添加调试信息显示
viewer_html = """
<!DOCTYPE HTML>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>全景图查看器</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/pannellum@2.5.6/build/pannellum.css"/>
    <script type="text/javascript" src="https://cdn.jsdelivr.net/npm/pannellum@2.5.6/build/pannellum.js"></script>
    <style>
    #panorama {
        width: 100vw;
        height: 100vh;
    }
    #toggleButton {
        position: fixed;
        top: 10px;
        right: 10px;
        z-index: 100;
        padding: 10px;
        background: rgba(0, 0, 0, 0.5);
        color: white;
        border: none;
        border-radius: 5px;
        cursor: pointer;
    }
    #debugInfo {
        position: fixed;
        top: 50px;
        right: 10px;
        z-index: 100;
        padding: 10px;
        background: rgba(0, 0, 0, 0.5);
        color: white;
        border-radius: 5px;
        font-size: 12px;
    }
    </style>
</head>
<body>
    <button id="toggleButton" onclick="toggleProjection()">切换到球面投影</button>
    <div id="debugInfo"></div>
    <div id="panorama"></div>
    <script>
    let currentType = 'cylindrical';
    let viewer;
    let imageConfig = null;
    
    function updateDebugInfo(config) {
        const debugDiv = document.getElementById('debugInfo');
        if (!config) return;  // 添加检查
        
        debugDiv.innerHTML = `
            当前模式: ${currentType}<br>
            图片尺寸: ${imageConfig ? imageConfig.width + 'x' + imageConfig.height : '未知'}<br>
            宽高比: ${imageConfig ? (imageConfig.width / imageConfig.height).toFixed(2) : '未知'}<br>
            垂直视: ${config.vaov ? config.vaov.toFixed(2) : '180.00'}°<br>
            最大俯仰角: ${config.maxPitch ? config.maxPitch.toFixed(2) : '90.00'}°<br>
            水平视场角: ${config.hfov ? config.hfov.toFixed(2) : '100.00'}°
        `;
    }
    
    // 加载图片配置
    fetch('image_config.json')
        .then(response => response.json())
        .then(config => {
            console.log('加载图片配置:', config);
            imageConfig = config;
            initViewer('cylindrical');
        })
        .catch(error => {
            console.error('加载配置失败:', error);
            document.getElementById('debugInfo').innerHTML = '配置加载失败: ' + error.message;
        });
    
    function initViewer(type) {
        if (viewer) {
            viewer.destroy();
        }
        
        const config = {
            "type": "equirectangular",
            "panorama": "input_image.jpg",
            "autoLoad": true,
            "haov": 360,
            "vaov": 180,
            "vOffset": 0,
            "hfov": 100,
            "minHfov": 50,
            "maxHfov": 120,
            "pitch": 0,
            "yaw": 0,
            "compass": false,
            "autoRotate": 0,
            "showControls": true,
            "mouseZoom": true,
            "draggable": true
        };
        
        if (type === 'cylindrical' && imageConfig) {
            const aspectRatio = imageConfig.width / imageConfig.height;
            console.log('宽高比:', aspectRatio);
            
            // 计算基础视场角，确保初始状态填满窗口高度
            const windowHeight = window.innerHeight;
            const imageHeight = imageConfig.height;
            const scale = windowHeight / imageHeight;
            const baseHfov = Math.min(120, 360 / aspectRatio);
            
            // 设置水平和垂直视场角
            config.haov = 120;  // 限制水平视角范围
            config.vaov = 90;   // 限制垂直视角范围
            config.hfov = baseHfov;
            
            // 限制俯仰角，防止超出图片边界
            config.maxPitch = 35;  // 上下移动范围
            config.minPitch = -35;
            
            // 设置缩放范围
            config.minHfov = baseHfov * 0.8;  // 最大放大到原始尺寸的0.8倍
            config.maxHfov = baseHfov * 1.2;  // 最小缩小到原始尺寸的1.2倍
            
            // 设置类型为圆柱投影
            config.type = 'cylindrical';
            
            console.log('柱面影配置:', {
                baseHfov,
                haov: config.haov,
                vaov: config.vaov,
                maxPitch: config.maxPitch,
                minPitch: config.minPitch,
                hfov: config.hfov,
                minHfov: config.minHfov,
                maxHfov: config.maxHfov
            });
        }
        
        console.log('最终配置:', config);
        updateDebugInfo(config);
        
        try {
            viewer = pannellum.viewer('panorama', config);
            
            // 监听窗口大小变化
            window.addEventListener('resize', function() {
                if (currentType === 'cylindrical' && viewer) {
                    const windowHeight = window.innerHeight;
                    const imageHeight = imageConfig.height;
                    const scale = windowHeight / imageHeight;
                    const baseHfov = Math.min(120, 360 / (imageConfig.width / imageConfig.height));
                    
                    // 更新视场角范围
                    viewer.setHfovBounds(baseHfov * 0.8, baseHfov * 1.2);
                    viewer.setHfov(baseHfov);
                }
            });
            
        } catch (e) {
            console.error('初始化查看器失败:', e);
            document.getElementById('debugInfo').innerHTML += '<br>初始化失败: ' + e.message;
        }
    }
    
    function toggleProjection() {
        const button = document.getElementById('toggleButton');
        if (currentType === 'cylindrical') {
            currentType = 'equirectangular';
            button.textContent = '切换到柱面投影';
        } else {
            currentType = 'cylindrical';
            button.textContent = '切换到球面影';
        }
        console.log('切换投影模式到:', currentType);
        initViewer(currentType);
    }
    </script>
</body>
</html>
"""

def find_free_port():
    """查找可用的端口"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port

# 在 start_server 函数之前添加自定义的 HTTP 处理器
class CustomHandler(http.server.SimpleHTTPRequestHandler):
    # 增加超时时间和最大请求大小
    timeout = 300
    max_content_length = 100 * 1024 * 1024  # 100MB

    def do_POST(self):
        if self.path == '/save_video':
            try:
                print("开始处理视频上传请求")
                content_length = int(self.headers['Content-Length'])
                print(f"接收到的数据大小: {content_length} bytes")
                
                video_data = self.rfile.read(content_length)
                print(f"成功读取视频数据: {len(video_data)} bytes")
                
                # 获取脚本所在目录的绝对路径
                base_dir = os.path.dirname(os.path.abspath(__file__))
                print(f"基础目录: {base_dir}")
                
                # 创建 video 目录
                video_dir = os.path.join(base_dir, "video")
                if not os.path.exists(video_dir):
                    os.makedirs(video_dir)
                    print(f"创建视频目录: {video_dir}")
                
                # 使用时间戳创建唯一文件名
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                webm_path = os.path.join(video_dir, f"temp_{timestamp}.webm")
                mp4_path = os.path.join(video_dir, f"panorama_{timestamp}.mp4")
                print(f"临时文件路径: {webm_path}")
                print(f"输出文件路径: {mp4_path}")
                
                # 保存 WebM 文件
                with open(webm_path, 'wb') as f:
                    f.write(video_data)
                print(f"WebM文件保存成功: {os.path.getsize(webm_path)} bytes")
                
                try:
                    # 检查 ffmpeg 是否可用
                    print("检查 ffmpeg...")
                    result = subprocess.run(['ffmpeg', '-version'], 
                                         capture_output=True, 
                                         text=True, 
                                         check=True)
                    print("ffmpeg 版本信息:", result.stdout.split('\n')[0])
                    
                    print(f"开始转换视频: {webm_path} -> {mp4_path}")
                    # 转换视频
                    result = subprocess.run([
                        'ffmpeg', '-i', webm_path,
                        '-c:v', 'libx264',
                        '-preset', 'ultrafast',
                        '-crf', '23',
                        mp4_path
                    ], capture_output=True, text=True, check=True)
                    
                    print("ffmpeg 输出:", result.stdout)
                    if result.stderr:
                        print("ffmpeg 警告/错误:", result.stderr)
                    
                    # 删除临时文件
                    if os.path.exists(webm_path):
                        os.remove(webm_path)
                        print("临时文件已删除")
                    
                    print(f"视频转换完成: {mp4_path}")
                    print(f"输出文件大小: {os.path.getsize(mp4_path)} bytes")
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'text/plain')
                    self.end_headers()
                    self.wfile.write(f"视频已保存为: panorama_{timestamp}.mp4".encode())
                    
                except subprocess.CalledProcessError as e:
                    print(f"ffmpeg 执行错误:")
                    print(f"命令: {' '.join(e.cmd)}")
                    print(f"返回码: {e.returncode}")
                    print(f"输出: {e.stdout}")
                    print(f"错误: {e.stderr}")
                    raise Exception(f"ffmpeg 错误: {e.stderr}")
                except FileNotFoundError:
                    print("未找到 ffmpeg 命令")
                    # 检查环境变量
                    print("PATH 环境变量:", os.environ.get('PATH'))
                    raise Exception("未找到 ffmpeg，请先安装 ffmpeg")
                    
            except Exception as e:
                print(f"视频处理失败: {str(e)}")
                print(f"错误类型: {type(e)}")
                import traceback
                print("详细错误信息:")
                print(traceback.format_exc())
                
                self.send_response(500)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"视频保存失败: {str(e)}".encode())
        else:
            super().do_POST()

# 修改 start_server 函数
def start_server(port=None):
    """启动本地服务器"""
    if port is None:
        port = find_free_port()
    
    try:
        httpd = socketserver.TCPServer(("", port), CustomHandler)
        print(f"服务器运行在 http://localhost:{port}")
        return httpd, port
    except OSError as e:
        print(f"端口 {port} 被占用，尝试其他端口")
        return start_server(None)

def get_local_ip():
    """获取本机局域网IP地址"""
    try:
        import socket
        hostname = socket.gethostname()
        # 获取所有网络接口的IP地址
        addresses = socket.getaddrinfo(hostname, None)
        
        # 筛选出IPv4地址
        for addr in addresses:
            ip = addr[4][0]
            # 检查是否是IPv4地址，并且不是回环地址
            if '.' in ip and not ip.startswith('127.'):
                # 如果找到了目标IP地址（10.250开头），直接返回
                if ip.startswith('10.250'):
                    return ip
        
        # 如果没有找到目标IP，返回第一个有效的IPv4地址
        for addr in addresses:
            ip = addr[4][0]
            if '.' in ip and not ip.startswith('127.'):
                return ip
                
        return "127.0.0.1"
    except Exception as e:
        print(f"获取IP地址时出错: {str(e)}")
        return "127.0.0.1"

def process_image(input_image):
    try:
        # 确保输出目录存在
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        # 使用相对路径保存文件
        input_path = os.path.join(OUTPUT_DIR, "input_image.jpg")
        input_image.save(input_path, format='JPEG', quality=95)
        print(f"图片已保存到: {input_path}")
        
        # 保存配置
        config_path = os.path.join(OUTPUT_DIR, "image_config.json")
        with open(config_path, "w") as f:
            json.dump({
                "width": input_image.width,
                "height": input_image.height
            }, f)
        
        # 启动本地服务器
        httpd, port = start_server()
        server_thread = threading.Thread(target=httpd.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        
        # 获取本机IP
        local_ip = get_local_ip()
        
        # 打开浏览器
        url = f"http://localhost:{port}/output/viewer.html"
        webbrowser.open(url)
        
        return f"全景图已生成，正在打开查看器...\n" \
               f"本地访问地址: http://localhost:{port}/output/viewer.html\n" \
               f"局域网访问地址: http://{local_ip}:{port}/output/viewer.html\n" \
               f"原始尺寸: {input_image.width}x{input_image.height}"
        
    except Exception as e:
        print(f"错误: {str(e)}")
        return f"处理失败: {str(e)}"

# 创建Gradio界面
iface = gr.Interface(
    fn=process_image,
    inputs=gr.Image(type="pil", label="上传全景图"),
    outputs=gr.Textbox(label="状态"),
    title="全景图查看器",
    description="上传全景图图片，自动打开查看器进行浏览（默认柱面投影模式）"
)

if __name__ == "__main__":
    # 在文件末尾添加命令行参数支持
    import argparse
    parser = argparse.ArgumentParser(description='全景图查看器')
    parser.add_argument('--image', help='要打开的图片路径')
    parser.add_argument('--share', action='store_true', help='启用局域网共享')
    parser.add_argument('--server-name', default='127.0.0.1', help='服务器IP地址')
    args = parser.parse_args()
    
    # 确保在output目录下运行服务器
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    if args.image:
        # 如果指定了图片路径，复制到output目录并重命名
        input_image = Image.open(args.image)
        process_image(input_image)
    
    # 启动界面，支持共享
    local_ip = get_local_ip()
    print(f"\n局域网访问地址: http://{local_ip}:7860")
    iface.launch(
        server_name="0.0.0.0",  # 允许所有IP访问
        share=True,
        inbrowser=False
    )

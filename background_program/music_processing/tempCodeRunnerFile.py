import socket
import pyaudio
import wave
import os
import time
import subprocess
import sys
import shutil
from pathlib import Path
import threading

# 安装必要的库
# pip install pyaudio playwright

class AudioRecorder:
    def __init__(self, host='127.0.0.1', port=5555, 
                 save_path="H:\\code\\Graduation_project\\music_processing\\midiPlay\\1_voice",
                 midi_path="H:\\code\\Graduation_project\\music_processing\\midiPlay\\2_midi"):
        # 音频参数设置
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 44100
        self.CHUNK = 1024
        self.recording = False
        self.frames = []
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.save_path = save_path
        self.midi_path = midi_path
        self.output_path = os.path.join(save_path, "voice_input.wav")
        self.midi_output_path = os.path.join(midi_path, "midi_input.mid")
        
        # SOME路径设置
        self.some_dir = r"H:\code\Graduation_project\music_processing\some-windows-x64-v0.0.1\some"
        self.run_bat_path = r"H:\code\Graduation_project\music_processing\some-windows-x64-v0.0.1\some\run.bat"
        
        # 确保保存目录存在
        os.makedirs(save_path, exist_ok=True)
        os.makedirs(midi_path, exist_ok=True)
        
        # 用户下载目录
        self.download_dir = os.path.join(os.path.expanduser("~"), "Downloads")
        
        # 网络服务器设置
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_socket.bind((host, port))
        print(f"录音服务已启动，监听于 {host}:{port}")
        print("可以通过TouchDesigner发送START和STOP命令控制录音")
        
    def start_recording(self):
        if not self.recording:
            self.recording = True
            self.frames = []
            self.stream = self.audio.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                frames_per_buffer=self.CHUNK
            )
            print("开始录音...")
            
    def stop_recording(self):
        if self.recording:
            self.recording = False
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
                self.stream = None
            print("停止录音...")
            self._save_audio()
            
    def _save_audio(self):
        if not self.frames:
            print("没有录制任何音频")
            return
            
        # 直接保存为WAV格式
        wf = wave.open(self.output_path, 'wb')
        wf.setnchannels(self.CHANNELS)
        wf.setsampwidth(self.audio.get_sample_size(self.FORMAT))
        wf.setframerate(self.RATE)
        wf.writeframes(b''.join(self.frames))
        wf.close()
        print(f"录音已保存到: {self.output_path}")
        
        # 使用Playwright自动化转换为MIDI
        try:
            self.convert_to_midi_using_playwright()
        except Exception as e:
            print(f"自动转换失败: {str(e)}")
            print("尝试使用备选方法...")
            self.convert_to_midi_manual()
            
    def convert_to_midi_using_playwright(self):
        """使用Playwright自动化浏览器操作将WAV文件转换为MIDI"""
        print("开始使用Playwright自动化WAV到MIDI转换...")
        
        # 复制录音文件到SOME工作目录
        some_base_dir = os.path.dirname(self.some_dir)
        temp_wav_path = os.path.join(some_base_dir, "input.wav")
        
        try:
            # 复制录音文件
            shutil.copy(self.output_path, temp_wav_path)
            print(f"已复制录音文件到: {temp_wav_path}")
            
            # 启动SOME服务器
            print(f"启动SOME服务器: {self.run_bat_path}")
            process = subprocess.Popen(
                self.run_bat_path, 
                shell=True, 
                cwd=os.path.dirname(self.run_bat_path)
            )
            
            # 等待服务器启动
            time.sleep(5)
            
            # 启动自动监视下载文件夹的线程
            monitor_thread = threading.Thread(
                target=self._monitor_downloads_folder,
                daemon=True
            )
            monitor_thread.start()
            
            # 使用Playwright自动化浏览器操作
            from playwright.sync_api import sync_playwright
            
            with sync_playwright() as p:
                print("启动浏览器...")
                browser = p.chromium.launch(headless=False)  # 设置为True可隐藏浏览器窗口
                page = browser.new_page(
                    accept_downloads=True
                )
                
                # 访问SOME网页
                print("访问SOME界面...")
                page.goto("http://localhost:7860/")
                
                # 等待页面完全加载 - 增加等待时间
                print("等待页面加载...")
                page.wait_for_load_state("networkidle")
                time.sleep(5)  # 增加额外等待时间
                
                # 尝试更精确地定位上传按钮
                print("尝试定位上传按钮...")
                
                # 尝试多种选择器来定位上传按钮
                selectors = [
                    "button:has-text('Input Audio File')",
                    "button >> text=Input Audio File",
                    "button[aria-label='Upload']",
                    "button:has(.svelte-upload)",
                    "button.svelte",
                    "[data-testid='Input Audio File']",
                    "label.upload",
                    "button:nth-child(1)",  # 尝试第一个按钮
                    "div.gradio-box button",  # Gradio容器中的按钮
                    "input[type=file]"  # 直接定位文件输入
                ]
                
                upload_element = None
                for selector in selectors:
                    try:
                        if page.is_visible(selector, timeout=2000):
                            print(f"找到上传元素: {selector}")
                            upload_element = selector
                            break
                    except:
                        continue
                
                if not upload_element:
                    # 如果无法找到元素，尝试截图记录当前页面状态
                    print("无法找到上传元素，保存页面截图...")
                    page.screenshot(path="some_interface.png")
                    print(f"已保存截图到: {os.path.abspath('some_interface.png')}")
                    
                    # 列出页面上所有按钮的文本以帮助调试
                    print("页面上的按钮文本:")
                    for button in page.query_selector_all("button"):
                        try:
                            print(f" - {button.inner_text()}")
                        except:
                            print(" - [无文本]")
                            
                    # 尝试直接使用文件输入元素
                    print("尝试直接使用文件输入元素...")
                    upload_element = "input[type=file]"
                
                # 上传文件
                try:
                    # 尝试直接使用文件输入元素上传，这种方式更可靠
                    print("尝试直接上传文件...")
                    # 增加等待时间
                    page.set_default_timeout(60000)  # 设置60秒超时
                    
                    # 查找文件输入元素
                    file_input = page.query_selector("input[type=file]")
                    if file_input:
                        # 使用JavaScript强制显示文件输入元素（如果它是隐藏的）
                        page.evaluate("""() => {
                            const fileInputs = document.querySelectorAll('input[type="file"]');
                            for (const input of fileInputs) {
                                input.style.opacity = '1';
                                input.style.display = 'block';
                                input.style.visibility = 'visible';
                            }
                        }""")
                        
                        # 直接设置文件
                        page.set_input_files("input[type=file]", temp_wav_path)
                        print("文件上传成功")
                    else:
                        print("找不到文件输入元素")
                        # 尝试点击可能的上传区域
                        try:
                            page.click("div.upload-box", timeout=5000)
                            page.set_input_files("input[type=file]", temp_wav_path)
                        except:
                            print("尝试点击上传区域失败")
                        
                except Exception as e:
                    print(f"文件上传过程中出错: {str(e)}")
                    # 继续尝试其他方法
                
                # 设置Tempo为120
                print("设置Tempo为120...")
                try:
                    # 尝试多种方式定位和设置Tempo输入框
                    tempo_selectors = [
                        "input[placeholder='120']",
                        "input.svelte-number",
                        "input[type=number]",
                        "input.tempo-input",
                        ".tempo-block input"
                    ]
                    
                    tempo_input = None
                    for selector in tempo_selectors:
                        try:
                            if page.is_visible(selector, timeout=2000):
                                tempo_input = selector
                                break
                        except:
                            continue
                    
                    if tempo_input:
                        # 清除并设置值
                        page.fill(tempo_input, "")  # 清除现有值
                        page.fill(tempo_input, "120")
                        print(f"已设置Tempo值: 120")
                    else:
                        print("未找到Tempo输入框，尝试使用默认值")
                except Exception as e:
                    print(f"设置Tempo时出错: {str(e)}")
                
                # 点击Submit按钮
                print("提交处理请求...")
                try:
                    # 尝试多种方式定位Submit按钮
                    submit_selectors = [
                        "button:has-text('Submit')",
                        "button >> text=Submit",
                        "button.submit-button",
                        "button.primary",
                        "button.svelte:has-text('Submit')",
                        "button[type=submit]"
                    ]
                    
                    submit_button = None
                    for selector in submit_selectors:
                        try:
                            if page.is_visible(selector, timeout=2000):
                                submit_button = selector
                                break
                        except:
                            continue
                    
                    if submit_button:
                        # 点击提交按钮
                        page.click(submit_button)
                        print("已点击Submit按钮")
                    else:
                        print("未找到Submit按钮，尝试其他方法")
                        # 尝试点击页面下方的按钮
                        buttons = page.query_selector_all("button")
                        if len(buttons) > 0:
                            # 点击最后一个按钮，通常是提交按钮
                            buttons[-1].click()
                            print("点击了页面上的最后一个按钮")
                except Exception as e:
                    print(f"点击Submit按钮时出错: {str(e)}")
                
                # 等待处理完成
                print("等待处理完成...")
                try:
                    # 等待进度条消失或下载按钮出现
                    page.wait_for_function("""() => {
                        // 检查是否有进度条并且不可见
                        const progressBars = document.querySelectorAll('.progress');
                        const noVisibleProgress = Array.from(progressBars).every(bar => 
                            getComputedStyle(bar).display === 'none' || 
                            getComputedStyle(bar).visibility === 'hidden');
                        
                        // 检查是否有下载按钮出现
                        const downloadButtons = document.querySelectorAll('button');
                        const hasDownloadButton = Array.from(downloadButtons).some(button => 
                            button.textContent.includes('Download') || 
                            button.innerText.includes('Download'));
                            
                        return noVisibleProgress || hasDownloadButton;
                    }""", timeout=60000)
                    
                    # 额外等待确保处理完成
                    time.sleep(3)
                except Exception as e:
                    print(f"等待处理完成时出错: {str(e)}")
                    # 继续尝试下载
                
                # 设置下载路径
                page.context.set_default_timeout(30000)  # 设置30秒超时
                
                # 尝试下载生成的MIDI文件
                print("尝试下载MIDI文件...")
                try:
                    # 基于您提供的截图，下载按钮是右侧的蓝色"79.0 B ↓"按钮
                    # 尝试多种方式定位这个下载按钮
                    download_selectors = [
                        "button.download",
                        "button.svelte-download",
                        "button:has-text('B ↓')",
                        "button.download-button",
                        # 右上角的下载按钮通常带有KB或MB和下载图标
                        "button:has-text('B')",
                        "a:has-text('B')",
                        "button.primary",
                        # 使用CSS选择器匹配右上角的蓝色按钮
                        "button.blue-button",
                        # 尝试直接通过颜色样式匹配
                        "button[style*='color: rgb(0, 125, 255)']",
                        "button[style*='background-color: rgb(0, 125, 255)']",
                        # 这是一个通用选择器，匹配右侧容器中的按钮
                        ".output-container button",
                        ".gradio-container .output-card button"
                    ]
                    
                    # 遍历所有可点击元素并打印其文本，帮助调试
                    print("页面上的可点击元素:")
                    buttons = page.query_selector_all("button, a")
                    for i, button in enumerate(buttons):
                        try:
                            text = button.inner_text().strip()
                            if text:
                                print(f"按钮 {i+1}: '{text}'")
                        except:
                            pass
                    
                    download_button = None
                    
                    # 首先尝试查找带有下载图标或B单位的按钮
                    for selector in download_selectors:
                        try:
                            if page.is_visible(selector, timeout=2000):
                                download_button = selector
                                print(f"找到下载按钮: {selector}")
                                break
                        except:
                            continue
                    
                    # 如果上面的方法失败，尝试查找右侧区域中的蓝色按钮
                    if not download_button:
                        print("尝试查找右侧区域中的蓝色按钮...")
                        try:
                            # 使用JavaScript查找匹配特征的按钮
                            download_button_js = page.evaluate("""() => {
                                // 查找右侧带有数字和下载图标的按钮
                                const buttons = Array.from(document.querySelectorAll('button, a'));
                                
                                // 查找匹配"xx.x B ↓"模式的按钮
                                for (const button of buttons) {
                                    const text = button.innerText || button.textContent;
                                    if (text && (
                                        text.includes('B ↓') || 
                                        text.includes('KB ↓') || 
                                        text.includes('MB ↓') ||
                                        (text.match(/\\d+(\\.\\d+)?\\s*[KMG]?B/) && button.style.color.includes('blue'))
                                    )) {
                                        return button;
                                    }
                                }
                                
                                // 右上角通常是蓝色突出显示的按钮
                                for (const button of buttons) {
                                    const style = window.getComputedStyle(button);
                                    if (
                                        (style.color.includes('rgb(0, 125, 255)') || 
                                         style.color.includes('rgb(0, 0, 255)') ||
                                         style.backgroundColor.includes('rgb(0, 125, 255)')) &&
                                        button.getBoundingClientRect().right > window.innerWidth / 2
                                    ) {
                                        return button;
                                    }
                                }
                                
                                return null;
                            }""")
                            
                            if download_button_js:
                                # 如果找到了按钮，使用JavaScript点击它
                                print("通过JavaScript找到下载按钮")
                                page.evaluate("button => button.click()", download_button_js)
                                
                                # 等待下载开始
                                time.sleep(3)
                                
                                # 查找已下载的文件
                                self._find_and_move_downloaded_midi_file()
                                return True
                        except Exception as e:
                            print(f"JavaScript下载尝试失败: {str(e)}")
                    
                    # 如果找到下载按钮，点击它
                    if download_button:
                        # 设置下载处理
                        with page.expect_download(timeout=30000) as download_info:
                            # 点击下载按钮
                            page.click(download_button)
                            print("已点击下载按钮")
                        
                        # 获取下载信息
                        download = download_info.value
                        print(f"下载文件: {download.suggested_filename}")
                        
                        # 保存下载文件
                        download_path = download.path()
                        print(f"临时文件路径: {download_path}")
                        
                        # 将下载的文件移动到目标路径
                        if os.path.exists(self.midi_output_path):
                            os.remove(self.midi_output_path)
                            
                        shutil.move(download_path, self.midi_output_path)
                        print(f"MIDI文件已保存到: {self.midi_output_path}")
                        return True
                    else:
                        print("尝试通过右侧输出区域查找下载链接...")
                        
                        # 截取当前页面状态
                        page.screenshot(path="output_area.png")
                        print(f"已保存输出区域截图: {os.path.abspath('output_area.png')}")
                        
                        # 尝试直接点击右上角有数字+B的元素
                        try:
                            # 使用XPath表达式查找包含"B"和数字的元素
                            page.click("xpath=//button[contains(text(), 'B')] | //a[contains(text(), 'B')]")
                            print("已点击包含'B'的元素")
                            time.sleep(3)
                            self._find_and_move_downloaded_midi_file()
                            return True
                        except Exception as e:
                            print(f"直接点击包含'B'的元素失败: {str(e)}")
                        
                        print("无法找到下载按钮，依赖文件监控机制")
                        # 延长等待时间，给监控线程更多时间
                        time.sleep(20)
                except Exception as e:
                    print(f"下载过程中出错: {str(e)}")
                    import traceback
                    traceback.print_exc()
                
                # 关闭浏览器
                browser.close()
            
            # 关闭SOME服务器进程
            try:
                process.terminate()
                print("SOME服务器已关闭")
            except:
                print("无法自动关闭SOME服务器")
                
            print("MIDI转换完成!")
            
        except Exception as e:
            print(f"使用Playwright自动化过程中出错: {str(e)}")
            import traceback
            traceback.print_exc()
            raise e
    
    def _monitor_downloads_folder(self):
        """监视下载文件夹，自动处理下载的MIDI文件"""
        print(f"开始监视下载文件夹: {self.download_dir}")
        
        # 获取监视前文件列表
        before_files = set(os.path.join(self.download_dir, f) 
                       for f in os.listdir(self.download_dir) 
                       if f.endswith('.mid'))
        
        # 持续监视30分钟
        end_time = time.time() + 1800
        
        while time.time() < end_time:
            time.sleep(2)  # 每2秒检查一次
            
            try:
                current_files = set(os.path.join(self.download_dir, f) 
                               for f in os.listdir(self.download_dir) 
                               if f.endswith('.mid'))
                
                # 检查是否有新文件
                new_files = current_files - before_files
                
                if new_files:
                    # 找到最新的MIDI文件
                    newest_file = max(new_files, key=os.path.getmtime)
                    
                    print(f"检测到新下载的MIDI文件: {newest_file}")
                    
                    # 等待文件下载完成
                    time.sleep(1)
                    
                    # 移动到目标位置
                    if os.path.exists(self.midi_output_path):
                        os.remove(self.midi_output_path)
                    
                    shutil.copy(newest_file, self.midi_output_path)
                    print(f"MIDI文件已复制到: {self.midi_output_path}")
                    
                    # 可选：删除原始下载文件
                    try:
                        os.remove(newest_file)
                    except:
                        pass
                    
                    return  # 完成监视
                
                # 更新文件列表
                before_files = current_files
                
            except Exception as e:
                print(f"监视过程中出错: {str(e)}")
    
    def convert_to_midi_manual(self):
        """备选方法：启动SOME并指导用户手动操作"""
        print("使用备选方法进行WAV到MIDI转换...")
        
        # 复制录音文件到SOME工作目录
        some_base_dir = os.path.dirname(self.some_dir)
        temp_wav_path = os.path.join(some_base_dir, "input.wav")
        
        try:
            # 复制录音文件
            shutil.copy(self.output_path, temp_wav_path)
            print(f"已复制录音文件到: {temp_wav_path}")
            
            # 启动SOME服务器
            print(f"启动SOME服务器: {self.run_bat_path}")
            process = subprocess.Popen(
                self.run_bat_path, 
                shell=True, 
                cwd=os.path.dirname(self.run_bat_path)
            )
            
            # 启动监视线程
            monitor_thread = threading.Thread(
                target=self._monitor_downloads_folder,
                daemon=True
            )
            monitor_thread.start()
            
            # 显示操作指南
            print("\n==========================================")
            print("SOME已启动，请按照以下步骤操作:")
            print("1. 在浏览器窗口中访问 http://localhost:7860")
            print("2. 点击'Input Audio File'按钮")
            print(f"3. 选择已复制的音频文件: {temp_wav_path}")
            print("4. 设置Tempo Value为120")
            print("5. 点击'Submit'按钮")
            print("6. 处理完成后点击'Download MIDI'下载生成的MIDI文件")
            print("7. 下载的文件会被自动移动到正确位置")
            print("==========================================\n")
            
            # 等待用户手动操作完成
            input("完成所有步骤后按Enter键继续...")
            
            # 尝试终止SOME进程
            try:
                process.terminate()
                print("SOME服务器已关闭")
            except:
                print("无法自动关闭SOME服务器，请手动关闭浏览器窗口")
                
        except Exception as e:
            print(f"备选方法过程中出错: {str(e)}")
    
    def record_loop(self):
        try:
            while True:
                if self.recording and self.stream:
                    try:
                        data = self.stream.read(self.CHUNK)
                        self.frames.append(data)
                    except Exception as e:
                        print(f"录制时出错: {str(e)}")
                        
                # 检查是否有来自TouchDesigner的命令
                try:
                    self.server_socket.settimeout(0.01)  # 非阻塞检查
                    data, addr = self.server_socket.recvfrom(1024)
                    command = data.decode().strip()
                    print(f"收到命令: {command}")
                    
                    if command == "START":
                        self.start_recording()
                    elif command == "STOP":
                        self.stop_recording()
                    elif command == "CONVERT":
                        # 直接转换已存在的音频文件
                        if os.path.exists(self.output_path):
                            try:
                                self.convert_to_midi_using_playwright()
                            except Exception as e:
                                print(f"自动转换失败: {str(e)}")
                                self.convert_to_midi_manual()
                        else:
                            print(f"错误: 未找到音频文件 {self.output_path}")
                except socket.timeout:
                    pass  # 没有数据，继续循环
                
                time.sleep(0.001)  # 小暂停避免CPU占用过高
                
        except KeyboardInterrupt:
            print("录音服务已停止")
            if self.recording:
                self.stop_recording()
            if self.audio:
                self.audio.terminate()
            self.server_socket.close()
            
if __name__ == "__main__":
    recorder = AudioRecorder()
    recorder.record_loop()
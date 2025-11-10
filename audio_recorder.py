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
        
        # 用户下载目录和临时目录
        self.download_dir = os.path.join(os.path.expanduser("~"), "Downloads")
        self.gradio_temp_dir = r"C:\Users\Ovo\AppData\Local\Temp\gradio"
        
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
    
    def _find_and_move_downloaded_midi_file(self):
        """查找并移动下载的MIDI文件"""
        print("正在查找下载的MIDI文件...")
        
        try:
            if os.path.exists(self.gradio_temp_dir):
                # 获取所有子文件夹，按修改时间排序
                subdirs = [d for d in os.listdir(self.gradio_temp_dir) 
                          if os.path.isdir(os.path.join(self.gradio_temp_dir, d))]
                
                if subdirs:
                    # 获取最新的子文件夹
                    latest_subdir = max(subdirs, 
                                      key=lambda d: os.path.getmtime(os.path.join(self.gradio_temp_dir, d)))
                    latest_dir_path = os.path.join(self.gradio_temp_dir, latest_subdir)
                    
                    # 在子文件夹中查找MIDI文件
                    for file in os.listdir(latest_dir_path):
                        if file.endswith('.mid'):
                            source_file = os.path.join(latest_dir_path, file)
                            print(f"找到MIDI文件: {source_file}")
                            
                            # 确保目标目录存在
                            os.makedirs(self.midi_path, exist_ok=True)
                            
                            # 目标文件路径，使用固定的文件名
                            destination = self.midi_output_path
                            
                            # 如果目标文件已存在，先删除
                            if os.path.exists(destination):
                                os.remove(destination)
                            
                            # 复制文件
                            shutil.copy2(source_file, destination)
                            print(f"MIDI文件已保存到: {destination}")
                            
                            return True
            
            return False
            
        except Exception as e:
            print(f"查找和移动文件时出错: {str(e)}")
            return False
    
    def _wait_for_processing_complete(self, page):
        """等待SOME处理完成"""
        print("等待SOME处理完成...")
        
        # 等待足够的处理时间
        time.sleep(15)
        
        # 可以通过检查页面状态来判断是否完成（可选）
        try:
            # 检查是否出现了结果区域
            page.wait_for_selector("button:has-text('↓')", timeout=10000)
            print("检测到处理已完成")
        except:
            print("未检测到完成信号，但继续查找文件")
            
        return True
            
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
            
            # 使用Playwright自动化浏览器操作
            from playwright.sync_api import sync_playwright
            
            with sync_playwright() as p:
                print("启动浏览器...")
                browser = p.chromium.launch(headless=False)
                page = browser.new_page()
                
                # 访问SOME网页
                print("访问SOME界面...")
                page.goto("http://localhost:7860/")
                
                # 等待页面完全加载
                print("等待页面加载...")
                page.wait_for_load_state("networkidle")
                time.sleep(3)
                
                # 上传文件
                try:
                    print("上传音频文件...")
                    # 使用更简单的文件上传方法
                    page.set_input_files("input[type=file]", temp_wav_path)
                    print("文件上传成功")
                    time.sleep(2)
                except Exception as e:
                    print(f"文件上传失败: {str(e)}")
                    raise e
                
                # 设置Tempo为120
                print("设置Tempo为120...")
                try:
                    # 查找并填写tempo输入框
                    tempo_inputs = page.query_selector_all("input[type=number]")
                    for input_elem in tempo_inputs:
                        placeholder = input_elem.get_attribute("placeholder")
                        if placeholder and "120" in placeholder:
                            page.fill(f"input[placeholder='{placeholder}']", "120")
                            print("已设置Tempo值: 120")
                            break
                    time.sleep(1)
                except Exception as e:
                    print(f"设置Tempo时出错: {str(e)}")
                
                # 点击Submit按钮
                print("提交处理请求...")
                try:
                    # 查找Submit按钮并点击
                    submit_buttons = page.query_selector_all("button")
                    for button in submit_buttons:
                        button_text = button.inner_text().strip()
                        if "Submit" in button_text or "提交" in button_text:
                            button.click()
                            print("已点击Submit按钮")
                            break
                    time.sleep(2)
                except Exception as e:
                    print(f"点击Submit按钮时出错: {str(e)}")
                
            # 等待处理完成
            self._wait_for_processing_complete(page)
            
            # 关闭浏览器
            browser.close()
            
            # 直接查找并移动MIDI文件（不需要下载）
            print("处理完成，查找生成的MIDI文件...")
            success = self._find_and_move_downloaded_midi_file()
            
            if not success:
                # 稍等一下再试一次
                print("等待2秒后再次查找...")
                time.sleep(2)
                success = self._find_and_move_downloaded_midi_file()
            
            # 关闭SOME服务器进程
            try:
                process.terminate()
                print("SOME服务器已关闭")
            except:
                print("无法自动关闭SOME服务器")
                
            # 最终检查是否成功获取了MIDI文件
            if os.path.exists(self.midi_output_path):
                print("MIDI转换完成!")
                return True
            else:
                print("未能获取MIDI文件，可能需要手动干预")
                return False
            
        except Exception as e:
            print(f"使用Playwright自动化过程中出错: {str(e)}")
            raise e
    
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
            
            # 显示操作指南
            print("\n==========================================")
            print("SOME已启动，请按照以下步骤操作:")
            print("1. 在浏览器窗口中访问 http://localhost:7860")
            print("2. 点击'Input Audio File'按钮")
            print(f"3. 选择已复制的音频文件: {temp_wav_path}")
            print("4. 设置Tempo Value为120")
            print("5. 点击'Submit'按钮")
            print("6. 等待处理完成")
            print("7. 文件会自动从临时目录复制到目标位置")
            print("==========================================\n")
            
            # 等待用户手动操作完成
            input("完成所有步骤后按Enter键继续...")
            
            # 查找并移动生成的MIDI文件
            print("查找生成的MIDI文件...")
            success = self._find_and_move_downloaded_midi_file()
            
            if success:
                print("MIDI文件处理成功！")
            else:
                print("未找到MIDI文件，请检查处理是否完成")
            
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
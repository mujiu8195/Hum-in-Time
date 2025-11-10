const express = require('express');
const cors = require('cors');
const fs = require('fs');
const path = require('path');
const bodyParser = require('body-parser');
const app = express();
const port = 5000;

// 启用CORS和JSON解析
app.use(cors());
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ extended: true, limit: '50mb' }));
app.use(express.static('public'));

// 为了处理原始二进制数据
app.use(bodyParser.raw({ type: 'audio/midi', limit: '50mb' }));

// 全局变量存储训练好的模型信息和输出路径
let trainedModel = null;
let outputDirectory = 'H:\\code\\Graduation_project\\music_processing\\midiPlay\\3_music';
// 新增默认训练次数配置
let defaultEpochs = 5; // 默认改为5

// WebSocket服务器用于实时通信
const WebSocket = require('ws');
const wss = new WebSocket.Server({ port: 5001 });

// 广播消息给所有连接的客户端
function broadcast(message) {
  wss.clients.forEach(client => {
    if (client.readyState === WebSocket.OPEN) {
      client.send(JSON.stringify(message));
    }
  });
}

// WebSocket连接处理
wss.on('connection', (ws) => {
  console.log('网页客户端已连接到WebSocket');
  
  // 如果已经有训练数据，通知客户端
  if (trainedModel) {
    ws.send(JSON.stringify({
      type: 'model_trained',
      data: trainedModel
    }));
  }
  
  // 处理来自客户端的消息
  ws.on('message', (message) => {
    try {
      const data = JSON.parse(message);
      console.log('收到WebSocket消息:', data);
      
      // 处理不同类型的消息
      if (data.type === 'training_progress') {
        // 广播训练进度
        broadcast(data);
      } else if (data.type === 'save_complete') {
        // 从客户端接收到保存完成的消息
        console.log('MIDI文件保存完成:', data.data.file_path);
      }
    } catch (error) {
      console.error('处理WebSocket消息错误:', error);
    }
  });
});

// API 路由：设置默认训练次数
app.post('/set_default_epochs', (req, res) => {
  try {
    console.log('收到设置默认训练次数请求:', req.body);
    const { epochs } = req.body;
    
    if (!epochs || typeof epochs !== 'number' || epochs < 1) {
      return res.status(400).json({ error: '训练次数必须是大于0的整数' });
    }
    
    defaultEpochs = Math.round(epochs);
    
    res.json({ 
      success: true, 
      message: `默认训练次数已设置为 ${defaultEpochs}`,
      defaultEpochs: defaultEpochs
    });
  } catch (error) {
    console.error('设置默认训练次数错误:', error);
    res.status(500).json({ error: error.message });
  }
});

// API 路由：从TouchDesigner获取MIDI文件路径进行训练
app.post('/train_with_path', async (req, res) => {
  try {
    console.log('收到训练请求:', req.body);
    const { file_path, epochs } = req.body;
    
    // 使用请求中的epochs或默认值
    const actualEpochs = epochs ? parseInt(epochs) : defaultEpochs;
    
    if (!file_path) {
      return res.status(400).json({ error: '缺少文件路径' });
    }
    
    // 检查文件是否存在
    if (!fs.existsSync(file_path)) {
      return res.status(404).json({ error: `文件 ${file_path} 不存在` });
    }
    
    // 保存训练信息
    trainedModel = {
      trained: true,
      filePath: file_path,
      epochs: actualEpochs,
      timestamp: new Date().toISOString()
    };
    
    // 通知所有连接的客户端开始训练
    broadcast({
      type: 'start_training',
      data: {
        file_path: file_path,
        epochs: actualEpochs
      }
    });
    
    res.json({ 
      success: true, 
      message: '已发送训练请求到网页',
      model_info: trainedModel
    });
  } catch (error) {
    console.error('训练错误:', error);
    res.status(500).json({ error: error.message });
  }
});

// API 路由：根据参数生成MIDI
app.post('/generate', (req, res) => {
  try {
    console.log('收到生成请求:', req.body);
    const { params_vector, save_path, file_name } = req.body;
    
    if (!params_vector || !Array.isArray(params_vector) || params_vector.length !== 4) {
      return res.status(400).json({ error: '参数向量必须是4个元素的数组' });
    }
    
    if (!trainedModel) {
      return res.status(400).json({ error: '请先训练模型' });
    }
    
    // 设置保存路径
    const actualSavePath = save_path || outputDirectory;
    const actualFileName = file_name || 'music_output.mid';
    
    // 通知所有连接的客户端生成MIDI
    broadcast({
      type: 'generate_midi',
      data: {
        params: params_vector,
        save_path: actualSavePath,
        file_name: actualFileName
      }
    });
    
    res.json({ 
      success: true, 
      message: '已发送生成请求到网页',
      params: params_vector,
      save_path: actualSavePath,
      file_name: actualFileName
    });
  } catch (error) {
    console.error('生成错误:', error);
    res.status(500).json({ error: error.message });
  }
});

// API 路由：更新参数
app.post('/update_params', (req, res) => {
  try {
    console.log('收到参数更新请求:', req.body);
    const { params } = req.body;
    
    if (!params || !Array.isArray(params) || params.length !== 4) {
      return res.status(400).json({ error: '参数必须是4个元素的数组' });
    }
    
    // 通知所有连接的客户端更新参数
    broadcast({
      type: 'update_params',
      data: {
        params: params
      }
    });
    
    res.json({ 
      success: true, 
      message: '参数已更新',
      params: params
    });
  } catch (error) {
    console.error('参数更新错误:', error);
    res.status(500).json({ error: error.message });
  }
});

// API 路由：设置输出目录
app.post('/set_output_directory', (req, res) => {
  try {
    console.log('收到设置输出目录请求:', req.body);
    const { directory } = req.body;
    
    if (!directory) {
      return res.status(400).json({ error: '缺少目录路径' });
    }
    
    // 确保目录存在
    if (!fs.existsSync(directory)) {
      fs.mkdirSync(directory, { recursive: true });
    }
    
    outputDirectory = directory;
    
    res.json({ 
      success: true, 
      message: '输出目录已设置',
      directory: outputDirectory
    });
  } catch (error) {
    console.error('设置输出目录错误:', error);
    res.status(500).json({ error: error.message });
  }
});

// API 路由：网页反馈训练状态
app.post('/training_status', (req, res) => {
  try {
    console.log('收到训练状态:', req.body);
    const { status, progress, model_info } = req.body;
    
    // 更新训练状态
    if (status === 'completed' && model_info) {
      console.log('训练完成，更新模型信息');
    }
    
    res.json({ success: true });
  } catch (error) {
    console.error('处理训练状态错误:', error);
    res.status(500).json({ error: error.message });
  }
});

// API 路由：网页反馈生成状态
app.post('/generation_status', (req, res) => {
  try {
    console.log('收到生成状态:', req.body);
    const { status, file_path } = req.body;
    
    // 记录生成状态
    if (status === 'saved' && file_path) {
      console.log('MIDI文件已保存到:', file_path);
    }
    
    res.json({ success: true });
  } catch (error) {
    console.error('处理生成状态错误:', error);
    res.status(500).json({ error: error.message });
  }
});

// 读取MIDI文件并返回其内容
app.get('/api/file', (req, res) => {
  try {
    const filePath = req.query.path;
    
    if (!fs.existsSync(filePath)) {
      return res.status(404).json({ error: `文件 ${filePath} 不存在` });
    }
    
    const fileContent = fs.readFileSync(filePath);
    res.contentType('audio/midi');
    res.send(fileContent);
  } catch (error) {
    console.error('读取文件错误:', error);
    res.status(500).json({ error: error.message });
  }
});

// 保存生成的MIDI文件
app.post('/api/save', (req, res) => {
  try {
    const { outputPath, fileName, fileData } = req.body;
    
    // 确保输出目录存在
    if (!fs.existsSync(outputPath)) {
      fs.mkdirSync(outputPath, { recursive: true });
    }
    
    // 解码Base64数据并保存文件
    const data = Buffer.from(fileData.split(',')[1], 'base64');
    const filePath = path.join(outputPath, fileName);
    
    fs.writeFileSync(filePath, data);
    console.log(`文件已保存到 ${filePath}`);
    res.json({ success: true, path: filePath });
  } catch (error) {
    console.error('保存文件错误:', error);
    res.status(500).json({ error: error.message });
  }
});

// 启动服务器
app.listen(port, () => {
  console.log(`服务器运行在 http://localhost:${port}`);
  console.log(`WebSocket服务器运行在 ws://localhost:5001`);
  console.log(`默认训练次数设置为: ${defaultEpochs}`);
});
import React, { useState } from 'react';
import { MarkdownRenderer, AIQuestionRenderer } from '../../components/MarkdownRenderer';

/**
 * Markdown渲染演示页面
 * 展示AI对话界面中的Markdown格式渲染效果
 */
const MarkdownRenderingDemo: React.FC = () => {
  const [selectedOption, setSelectedOption] = useState<string>('');
  const [showResult, setShowResult] = useState(false);

  // 示例问题数据
  const sampleQuestion = {
    question: "**一个问题：** 计算汽车滑动摩擦时水平路面的总摩擦面积（$S_总$），需要用到的物理量是？",
    options: [
      "A. 每个轮胎接触面积（$S_单个$）和轮胎数量（$n$）",
      "B. 总质量（$m$）和重力加速度（$g$）", 
      "C. 总质量（$m$）和每个轮胎接触面积（$S_单个$）",
      "D. 汽车行驶速度（$v$）和轮胎数量（$n$）"
    ],
    correctAnswer: "A"
  };

  const handleOptionSelect = (option: string) => {
    setSelectedOption(option);
    setShowResult(false);
  };

  const handleCheckAnswer = () => {
    setShowResult(true);
  };

  const handleReset = () => {
    setSelectedOption('');
    setShowResult(false);
  };

  // 示例AI解释文本
  const explanationText = `
没关系，这是一个常见的困惑点。

让我来解释一下为什么需要这些物理量：

计算**总摩擦面积**时，我们需要知道：
- **每个轮胎的接触面积**（$S_单个$）：这是单个轮胎与地面的接触面积
- **轮胎数量**（$n$）：汽车有几个轮胎与地面接触

总摩擦面积的计算公式是：
$$S_总 = S_单个 \times n$$

这就像计算房间的总面积一样，你需要知道每个房间的面积和房间的数量。

现在请重新选择正确答案：
  `;

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4">
        <div className="bg-white rounded-lg shadow-lg p-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-8 text-center">
            AI导师对话界面 - Markdown渲染演示
          </h1>

          {/* AI头像和消息气泡 */}
          <div className="space-y-6">
            {/* AI消息 */}
            <div className="flex items-start space-x-4">
              <div className="flex-shrink-0">
                <div className="w-10 h-10 bg-blue-500 rounded-full flex items-center justify-center">
                  <span className="text-white font-bold text-sm">AI</span>
                </div>
              </div>
              <div className="flex-1 bg-blue-50 rounded-lg p-4 max-w-3xl">
                <AIQuestionRenderer
                  question={sampleQuestion.question}
                  options={sampleQuestion.options}
                  onOptionSelect={handleOptionSelect}
                  selectedOption={selectedOption}
                  showResult={showResult}
                  correctAnswer={sampleQuestion.correctAnswer}
                />
              </div>
            </div>

            {/* 用户选择显示 */}
            {selectedOption && (
              <div className="flex items-start space-x-4 justify-end">
                <div className="bg-green-100 rounded-lg p-4 max-w-xs">
                  <p className="text-gray-800">
                    我选择：<strong>{selectedOption}</strong>
                  </p>
                </div>
                <div className="flex-shrink-0">
                  <div className="w-10 h-10 bg-green-500 rounded-full flex items-center justify-center">
                    <span className="text-white font-bold text-sm">我</span>
                  </div>
                </div>
              </div>
            )}

            {/* AI解释消息（错误答案时显示） */}
            {showResult && selectedOption !== sampleQuestion.correctAnswer && (
              <div className="flex items-start space-x-4">
                <div className="flex-shrink-0">
                  <div className="w-10 h-10 bg-blue-500 rounded-full flex items-center justify-center">
                    <span className="text-white font-bold text-sm">AI</span>
                  </div>
                </div>
                <div className="flex-1 bg-blue-50 rounded-lg p-4 max-w-3xl">
                  <MarkdownRenderer content={explanationText} />
                  
                  {/* 重新提问 */}
                  <div className="mt-6 pt-4 border-t border-blue-200">
                    <AIQuestionRenderer
                      question={sampleQuestion.question}
                      options={sampleQuestion.options}
                      onOptionSelect={handleOptionSelect}
                      selectedOption=""
                      showResult={false}
                    />
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* 控制按钮 */}
          <div className="mt-8 flex justify-center space-x-4">
            {selectedOption && !showResult && (
              <button
                onClick={handleCheckAnswer}
                className="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
              >
                检查答案
              </button>
            )}
            <button
              onClick={handleReset}
              className="px-6 py-2 bg-gray-500 text-white rounded-lg hover:bg-gray-600 transition-colors"
            >
              重置演示
            </button>
          </div>

          {/* 技术说明 */}
          <div className="mt-12 bg-gray-100 rounded-lg p-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">技术实现说明</h2>
            <div className="space-y-3 text-gray-700">
              <p>
                <strong>1. JSON格式AI响应：</strong> AI返回结构化的JSON数据，包含问题、选项和正确答案。
              </p>
              <p>
                <strong>2. 前后端分离：</strong> 前端只显示问题和选项，正确答案由后端程序判断。
              </p>
              <p>
                <strong>3. Markdown渲染：</strong> 支持数学公式（LaTeX）、强调文本、列表等格式。
              </p>
              <p>
                <strong>4. 交互式选择：</strong> 用户选择答案后，程序自动判断对错并给出相应反馈。
              </p>
              <p>
                <strong>5. 苏格拉底式教学：</strong> 错误答案时提供解释，然后重新提问，引导学生思考。
              </p>
            </div>
          </div>

          {/* 示例JSON数据 */}
          <div className="mt-8 bg-gray-900 rounded-lg p-6">
            <h3 className="text-lg font-semibold text-white mb-4">示例AI响应JSON：</h3>
            <pre className="text-green-400 text-sm overflow-x-auto">
{`{
  "question": "**一个问题：** 计算汽车滑动摩擦时水平路面的总摩擦面积（$S_总$），需要用到的物理量是？",
  "options": [
    "A. 每个轮胎接触面积（$S_单个$）和轮胎数量（$n$）",
    "B. 总质量（$m$）和重力加速度（$g$）",
    "C. 总质量（$m$）和每个轮胎接触面积（$S_单个$）",
    "D. 汽车行驶速度（$v$）和轮胎数量（$n$）"
  ],
  "correct_option": "A"
}`}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MarkdownRenderingDemo;

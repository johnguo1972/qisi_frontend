import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

/**
 * Markdown渲染器组件
 * 支持数学公式渲染和自定义样式
 */
export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({
  content,
  className = '',
}) => {
  return (
    <div className={`markdown-content ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          // 自定义段落样式
          p: ({ children }) => (
            <p className="mb-3 text-gray-800 leading-relaxed">{children}</p>
          ),
          // 自定义强调文本样式
          strong: ({ children }) => (
            <strong className="font-semibold text-gray-900">{children}</strong>
          ),
          // 自定义列表样式
          ul: ({ children }) => (
            <ul className="mb-4 space-y-2">{children}</ul>
          ),
          li: ({ children }) => (
            <li className="flex items-start">
              <span className="inline-block w-6 h-6 mr-3 mt-0.5 bg-blue-100 text-blue-600 rounded-full text-sm font-medium flex items-center justify-center flex-shrink-0">
                {/* 这里可以根据选项内容提取字母 */}
                {typeof children === 'string' && children.match(/^[A-D]\./) 
                  ? children.charAt(0) 
                  : '•'}
              </span>
              <span className="flex-1 text-gray-800">{children}</span>
            </li>
          ),
          // 自定义代码块样式
          code: ({ inline, children }) => {
            if (inline) {
              return (
                <code className="px-1.5 py-0.5 bg-gray-100 text-gray-800 rounded text-sm font-mono">
                  {children}
                </code>
              );
            }
            return (
              <pre className="bg-gray-50 p-4 rounded-lg overflow-x-auto mb-4">
                <code className="text-sm font-mono text-gray-800">{children}</code>
              </pre>
            );
          },
          // 自定义标题样式
          h1: ({ children }) => (
            <h1 className="text-xl font-bold text-gray-900 mb-4">{children}</h1>
          ),
          h2: ({ children }) => (
            <h2 className="text-lg font-semibold text-gray-900 mb-3">{children}</h2>
          ),
          h3: ({ children }) => (
            <h3 className="text-base font-medium text-gray-900 mb-2">{children}</h3>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
};

/**
 * 专门用于渲染AI问题的组件
 */
interface AIQuestionRendererProps {
  question: string;
  options: string[];
  onOptionSelect?: (option: string) => void;
  selectedOption?: string;
  showResult?: boolean;
  correctAnswer?: string;
}

export const AIQuestionRenderer: React.FC<AIQuestionRendererProps> = ({
  question,
  options,
  onOptionSelect,
  selectedOption,
  showResult = false,
  correctAnswer,
}) => {
  const getOptionLetter = (option: string): string => {
    const match = option.match(/^([A-D])\./);
    return match ? match[1] : '';
  };

  const getOptionContent = (option: string): string => {
    return option.replace(/^[A-D]\.\s*/, '');
  };

  const getOptionStyle = (option: string): string => {
    const letter = getOptionLetter(option);
    let baseStyle = "w-full p-4 text-left border-2 rounded-lg transition-all duration-200 ";
    
    if (showResult && correctAnswer) {
      if (letter === correctAnswer) {
        baseStyle += "border-green-500 bg-green-50 text-green-800 ";
      } else if (letter === selectedOption) {
        baseStyle += "border-red-500 bg-red-50 text-red-800 ";
      } else {
        baseStyle += "border-gray-200 bg-gray-50 text-gray-600 ";
      }
    } else if (selectedOption === letter) {
      baseStyle += "border-blue-500 bg-blue-50 text-blue-800 ";
    } else {
      baseStyle += "border-gray-200 bg-white text-gray-800 hover:border-blue-300 hover:bg-blue-50 ";
    }
    
    return baseStyle;
  };

  return (
    <div className="ai-question-container">
      {/* 问题文本 */}
      <div className="mb-6">
        <MarkdownRenderer 
          content={question} 
          className="text-lg font-medium text-gray-900"
        />
      </div>
      
      {/* 选项列表 */}
      <div className="space-y-3">
        {options.map((option, index) => {
          const letter = getOptionLetter(option);
          const content = getOptionContent(option);
          
          return (
            <button
              key={index}
              onClick={() => onOptionSelect?.(letter)}
              disabled={showResult}
              className={getOptionStyle(option)}
            >
              <div className="flex items-start">
                <span className="inline-flex items-center justify-center w-8 h-8 mr-4 bg-current text-white rounded-full text-sm font-bold flex-shrink-0 opacity-80">
                  {letter}
                </span>
                <span className="flex-1 text-left">
                  <MarkdownRenderer content={content} />
                </span>
              </div>
            </button>
          );
        })}
      </div>
      
      {/* 结果提示 */}
      {showResult && (
        <div className="mt-4 p-4 rounded-lg">
          {selectedOption === correctAnswer ? (
            <div className="flex items-center text-green-700 bg-green-50 p-3 rounded-lg">
              <svg className="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              <span className="font-medium">回答正确！</span>
            </div>
          ) : (
            <div className="flex items-center text-red-700 bg-red-50 p-3 rounded-lg">
              <svg className="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
              <span className="font-medium">回答错误，正确答案是 {correctAnswer}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

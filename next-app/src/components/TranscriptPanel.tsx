import React from 'react';

interface TextChunk {
  text: string;
  bbox: number[]; 
  page_num: number; 
}

interface TranscriptPanelProps {
  extractedText: TextChunk[];
  onTextClick: (bbox: number[], pageNum: number) => void;
}

const TranscriptPanel: React.FC<TranscriptPanelProps> = ({
  extractedText,
  onTextClick,
}) => {
  return (
    <div className="h-[800px] bg-white rounded-lg shadow overflow-hidden">
      <div className="p-4 border-b bg-gray-50">
        <h2 className="text-xl font-bold text-gray-800">Transcript</h2>
      </div>
      <div className="h-[calc(100%-4rem)] overflow-y-auto p-4">
        {extractedText?.length === 0 ? (
          <p className="text-gray-500 text-center">No extracted text available</p>
        ) : (
          <div className="space-y-3">
            {extractedText.map((chunk, index) => (
              <div
                key={index}
                onClick={() => onTextClick(chunk.bbox, chunk.page_num)}
                className="p-3 bg-gray-50 rounded hover:bg-blue-50 cursor-pointer transition-colors"
              >
                <p className="text-gray-800">{chunk.text}</p>
                <span className="text-xs text-gray-500">
                  Page {chunk.page_num}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default TranscriptPanel;

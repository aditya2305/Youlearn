import React from 'react';

interface Transcript {
  text: string;
  bbox: number[];
  page_num?: number;
}

interface TranscriptListProps {
  transcripts: Transcript[];
  onTranscriptClick: (text: string, bbox: number[]) => void;
  selectedText: string | null;
}

const TranscriptList = ({ transcripts, onTranscriptClick, selectedText }: TranscriptListProps) => {
  return (
    <div className="h-[750px] overflow-y-auto border-l p-4">
      <h2 className="text-lg font-bold mb-4">Extracted Text</h2>
      {transcripts.map((transcript, index) => (
        <div
          key={`${transcript.text}-${index}`}
          className={`p-2 mb-2 cursor-pointer rounded ${
            selectedText === transcript.text ? 'bg-blue-100 border-blue-500' : 'hover:bg-gray-50'
          }`}
          onClick={() => onTranscriptClick(transcript.text, transcript.bbox)}
        >
          {transcript.text}
        </div>
      ))}
    </div>
  );
};

export default TranscriptList;
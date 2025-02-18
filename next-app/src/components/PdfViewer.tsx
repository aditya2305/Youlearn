import React, { useRef } from 'react';
import { Viewer, Worker } from '@react-pdf-viewer/core';
import { defaultLayoutPlugin } from '@react-pdf-viewer/default-layout';
import '@react-pdf-viewer/core/lib/styles/index.css';
import '@react-pdf-viewer/default-layout/lib/styles/index.css';
import BoundingBox from './BoundingBox';

interface PdfViewerProps {
  url: string;
  currentPage: number;
  selectedBBox: number[] | null;
  onPageChange: (pageNum: number) => void;
}

const PdfViewer: React.FC<PdfViewerProps> = ({
  url,
  currentPage,
  selectedBBox,
  onPageChange,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const defaultLayoutPluginInstance = defaultLayoutPlugin();

  return (
    <div ref={containerRef} className="relative h-[800px] bg-white rounded-lg overflow-hidden">
      <Worker workerUrl="https://unpkg.com/pdfjs-dist@3.4.120/build/pdf.worker.min.js">
        <Viewer
          fileUrl={url}
          plugins={[defaultLayoutPluginInstance]}
          onPageChange={(e) => onPageChange(e.currentPage)}
        />
        {selectedBBox && (
          <BoundingBox
            bbox={selectedBBox}
            pageNumber={currentPage}
            containerRef={containerRef}
          />
        )}
      </Worker>
    </div>
  );
};

export default PdfViewer;

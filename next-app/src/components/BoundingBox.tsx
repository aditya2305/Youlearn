import React, { useEffect, useState, MutableRefObject } from 'react';

interface BoundingBoxProps {
  bbox: number[];
  pageNumber: number;
  containerRef: MutableRefObject<HTMLDivElement | null>;
}

const BoundingBox: React.FC<BoundingBoxProps> = ({
  bbox,
  pageNumber,
  containerRef
}) => {
  const [position, setPosition] = useState({
    left: 0,
    top: 0,
    width: 0,
    height: 0,
  });

  useEffect(() => {
    if (!containerRef.current) return;

    const container = containerRef.current;

    const pageElement = container.querySelector(
      `[data-testid="core__page-layer-${pageNumber - 1}"]`
    ) as HTMLDivElement | null;

    if (!pageElement) {
      console.warn(`Could not find page element for page #${pageNumber}`);
      return;
    }

    const pageCanvas = pageElement.querySelector('.rpv-core__canvas-layer canvas');
    if (!pageCanvas) {
      console.warn(`Could not find canvas for page #${pageNumber}`);
      return;
    }

    const canvasRect = pageCanvas.getBoundingClientRect();
    const containerRect = container.getBoundingClientRect();

    const x0 = bbox[0] * canvasRect.width;
    const y0 = bbox[1] * canvasRect.height;
    const x1 = bbox[2] * canvasRect.width;
    const y1 = bbox[3] * canvasRect.height;

    setPosition({
      left: canvasRect.left - containerRect.left + x0,
      top: canvasRect.top - containerRect.top + y0,
      width: x1 - x0,
      height: y1 - y0,
    });
  }, [bbox, pageNumber, containerRef]);

  return (
    <div
      style={{
        position: 'absolute',
        left: position.left,
        top: position.top,
        width: position.width,
        height: position.height,
        border: '2px solid red',
        backgroundColor: 'rgba(255, 0, 0, 0.1)',
        pointerEvents: 'none',
        zIndex: 1000,
      }}
    />
  );
};

export default BoundingBox;

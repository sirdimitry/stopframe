// Persistent Apple Vision worker. Images stay on the local machine.
import Foundation
import Vision
import CoreML
import ImageIO

func reply(_ object: [String: Any]) {
    if let data = try? JSONSerialization.data(withJSONObject: object),
       let line = String(data: data, encoding: .utf8) {
        print(line)
        fflush(stdout)
    }
}

// Measure opening perpendicular to the longest contour axis, accounting for
// face roll and non-square face bounding boxes. Missing geometry fails closed.
func openingRatio(_ region: VNFaceLandmarkRegion2D?, _ box: CGRect, _ size: CGSize) -> Double {
    guard let region = region, region.pointCount >= 4 else { return 0 }
    let points = region.normalizedPoints.map {
        CGPoint(x: CGFloat($0.x) * box.width * size.width,
                y: CGFloat($0.y) * box.height * size.height)
    }
    return contourOpening(points)
}

func contourOpening(_ points: [CGPoint]) -> Double {
    guard points.count >= 4 else { return 0 }
    var longest = 0.0
    var axis = CGPoint.zero
    for a in points {
        for b in points {
            let dx = b.x - a.x, dy = b.y - a.y
            let length = hypot(dx, dy)
            if length > longest { longest = length; axis = CGPoint(x: dx, y: dy) }
        }
    }
    guard longest > 0 else { return 0 }
    let projections = points.map { (-$0.x * axis.y + $0.y * axis.x) / longest }
    return Double((projections.max()! - projections.min()!) / longest)
}

if CommandLine.arguments.contains("--self-test") {
    let eye = [CGPoint(x: 0, y: 0), CGPoint(x: 4, y: 1), CGPoint(x: 10, y: 0), CGPoint(x: 4, y: -1)]
    let closed = eye.map { CGPoint(x: $0.x, y: $0.y * 0.1) }
    let rotated = eye.map { CGPoint(x: -$0.y, y: $0.x) }
    precondition(abs(contourOpening(eye) - 0.2) < 0.001)
    precondition(contourOpening(closed) < 0.15)
    precondition(abs(contourOpening(rotated) - contourOpening(eye)) < 0.001)
    precondition(contourOpening([]) == 0)
    reply(["geometry": "ok"])
    exit(0)
}

let request = VNDetectFaceLandmarksRequest()
request.preferBackgroundProcessing = true
var compute: [String: String] = [:]
if #available(macOS 14.0, *) {
    do {
        for (stage, devices) in try request.supportedComputeStageDevices {
            // Leave scheduling to Vision when no accelerator is supported.
            // Use the Neural Engine where this request explicitly supports it.
            let neural = devices.first { if case .neuralEngine = $0 { return true }; return false }
            if let neural = neural {
                request.setComputeDevice(neural, for: stage)
                compute[stage.rawValue] = "neuralEngine"
            } else {
                compute[stage.rawValue] = "automatic"
            }
        }
    } catch { compute["deviceQuery"] = "automatic" }
}

while let line = readLine() {
    autoreleasepool {
        do {
            guard let data = line.data(using: .utf8),
                  let input = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
                throw NSError(domain: "StopFrame", code: 1)
            }
            if input["cmd"] as? String == "quit" { exit(0) }
            if input["cmd"] as? String == "ping" {
                reply(["ready": true, "backend": "appleVision", "compute": compute])
                return
            }
            guard let path = input["frame_path"] as? String,
                  let source = CGImageSourceCreateWithURL(URL(fileURLWithPath: path) as CFURL, nil),
                  let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
                throw NSError(domain: "StopFrame", code: 2)
            }
            let handler = VNImageRequestHandler(cgImage: image, orientation: .up)
            try handler.perform([request])
            let faces = request.results ?? []
            if faces.isEmpty { reply(["face_found": false]); return }
            let size = CGSize(width: image.width, height: image.height)
            var eyesOpen = true, mouthClosed = true
            var ratios: [[Double]] = []
            for face in faces {
                let left = openingRatio(face.landmarks?.leftEye, face.boundingBox, size)
                let right = openingRatio(face.landmarks?.rightEye, face.boundingBox, size)
                let mouth = openingRatio(face.landmarks?.innerLips, face.boundingBox, size)
                eyesOpen = eyesOpen && min(left, right) > 0.15
                mouthClosed = mouthClosed && face.landmarks?.innerLips != nil && mouth < 0.15
                ratios.append([left, right, mouth])
            }
            let box = faces[0].boundingBox
            reply(["face_found": true, "eyes_open": eyesOpen, "mouth_closed": mouthClosed,
                   "bbox": [Int(box.minX * size.width), Int((1 - box.maxY) * size.height),
                            Int(box.width * size.width), Int(box.height * size.height)],
                   "ratios": ratios])
        } catch { reply(["error": String(describing: error)]) }
    }
}

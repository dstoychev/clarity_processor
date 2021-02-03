import numpy as np
import cv2
import typing


class Processor:
    """Processing of image data obtained through Aurox Clarity devices.

    Args:
        cal_img: image of the calibration pattern.
    """

    # Setup SimpleBlobDetector parameters - constant, so shared between
    # instances.
    _params = cv2.SimpleBlobDetector_Params()

    # Change thresholds
    _params.minThreshold = 20
    _params.maxThreshold = 200
    _params.thresholdStep = 10

    _params.filterByColor = True
    _params.blobColor = 255

    # Filter by Area.
    _params.filterByArea = True
    _params.minArea = 10
    _params.maxArea = 40

    # Filter by Circularity
    _params.filterByCircularity = True
    _params.minCircularity = 0.1
    _params.maxCircularity = 1.0

    # Filter by Convexity
    _params.filterByConvexity = True
    _params.minConvexity = 0.5
    _params.maxConvexity = 1.0

    # Also share blob detector between instances - resource footprint seems to
    # be negligible.
    _detector = cv2.SimpleBlobDetector_create(_params)

    @classmethod
    def _find_spots(cls, img: np.ndarray, border: typing.Optional[int] = 5):
        """Find all spots in img, excluding those within border of the edges.

        Parameters
        ----------
        img : array-like
            an image containing spots
        border : int
            The width of a border, in pixels.

        Returns
        -------
        pos : array([[float, float],])
            An array of cartesian positions for spots found in the image,
            excluding those that lie within the border region.
        """
        keypoints = cls._detector.detect(img)
        n = len(keypoints)
        pos = np.asarray([keypoints[i].pt for i in range(n)])
        h, w = img.shape
        return pos[
            (pos[:, 0] > border)
            & (pos[:, 0] < (w - border))
            & (pos[:, 1] > border)
            & (pos[:, 1] < (h - border)),
            :,
        ]

    @staticmethod
    def _find_penrose(pos: np.ndarray):
        """Find Penrose groups in a set of spots.

        Parameters
        ----------
        pos : array-like [[float, float],]
            A list of co-ordinate pairs defining cartesion spot positions.

        Returns
        -------
        dmid : float
            mean radius of penrose stars

        pos6 : array([[float, float],])
            Positions of the central point in each Penrose group.

        c_offset : array([[float, float],])
            Offset between central spot and centroid of each Penrose group.


        """
        n = len(pos)
        # Determine spot-spot separations
        sep = np.zeros((n, n))
        for i in range(n):
            sep[i, :] = np.hypot(*(pos - pos[i]).T)
        # Determine threshold based on distribution of spot separations.
        # dmid = np.sort(sep.ravel())[int(3.5 * n)]
        dmid = np.partition(sep.ravel(), int(3.5 * n))[int(3.5 * n)]
        dlow = 0.91 * dmid
        dhi = 1.09 * dmid
        # number of neighbours between threshold distances from each spot
        neighbourcount = np.sum((sep > dlow) & (sep < dhi), 0)
        # Indices of 6-way co-ordianted spots.
        indices = np.flatnonzero(neighbourcount == 6)
        # Positions of 6-way co-ordinated spots at centre of 7-spot clusters.
        pos6 = pos[indices]
        # Find offset between each 6-way co-ordinated point and centroid of its
        # neighbours.
        c_offset = np.empty_like(pos6)
        for i, idx in enumerate(indices):
            neighbours = np.flatnonzero(
                (sep[idx, :] > dlow) & (sep[idx, :] < dhi)
            )
            c_offset[i] = np.sum(pos[neighbours] - pos[idx], axis=0)
        return (dmid, pos6, c_offset)

    def __init__(self, cal_img: np.ndarray):
        self.width = int(np.size(cal_img, 1) / 2)
        self.height = np.size(cal_img, 0)

        # Normalise and convert to 8-bit
        im = np.zeros_like(cal_img, dtype="uint8")
        cv2.normalize(cal_img, im, 0, 255, cv2.NORM_MINMAX, cv2.CV_8U)

        # find all spots in left and right images
        posl = self._find_spots(im[:, 0 : self.width])
        nl = len(posl)
        posr = self._find_spots(im[:, self.width :])
        nr = len(posr)

        # Reduce parameter-space for determining the affine transform by
        # finding 6-way co-ordinated spots that lie at the centre of Penrose
        # stars. Find star radius, central spot positions, and centroid offsets
        # for left and right images.
        (dmidl, pos6l, diff6l) = self._find_penrose(posl)
        (dmidr, pos6r, diff6r) = self._find_penrose(posr)

        # find matched 6-way co-ordinated spot pairs
        pmatch6l = []
        pmatch6r = []

        for i in range(
            len(pos6l)
        ):  # loop over all 6-way co-ordinated left spots
            dist6 = np.hypot(
                pos6r[:, 1] - pos6l[i, 1],
                self.width - 1 - pos6r[:, 0] - pos6l[i, 0],
            )
            # the distance of all right spots from this left spot
            distoffs = np.hypot(
                diff6l[i, 1] - diff6r[:, 1], diff6l[i, 0] + diff6r[:, 0]
            )
            # the distance between the right and left 6-spot centroids
            for j in range(
                len(pos6r)
            ):  # loop over all 6-way co-ordinated spots on right
                if (dist6[j] < 4 * dmidl) & (distoffs[j] < dmidl / 4):
                    # select spots as pairs if they are close enough and if the
                    # centroids are close enough
                    pmatch6l = np.append(pmatch6l, pos6l[i, :])
                    # add to list of left and right matched spots
                    pmatch6r = np.append(pmatch6r, pos6r[j, :])
        nmatch6 = int(len(pmatch6l) / 2)
        pmatch6l = np.reshape(pmatch6l, (nmatch6, 2))
        pmatch6r = np.reshape(pmatch6r, (nmatch6, 2))

        # find affine transform based on 6-way matches
        [retval, p_affine] = cv2.solve(
            np.c_[pmatch6r, np.ones(nmatch6)], pmatch6l, flags=cv2.DECOMP_SVD
        )

        # transform all right spot positions to find matches on left
        posrt = np.matmul(np.c_[posr, np.ones(nr)], p_affine)

        pmatchl = []
        pmatchr = []
        for i in range(nl):
            dist = np.hypot(*(posl[i] - posrt).T)
            mind = min(dist)
            if mind < 5:
                pmatchl = np.append(pmatchl, posl[i, :])
                pmatchr = np.append(pmatchr, posr[np.argmin(dist), :])

        nmatch = int(len(pmatchl) / 2)
        pmatchl = np.reshape(pmatchl, (nmatch, 2))
        pmatchr = np.reshape(pmatchr, (nmatch, 2))

        # Determine polynomial transform for all matched pairs
        # Sum terms: 1, x, y, x^2, y^2, x*y, x^2*y, x*y^2, x^3, y^3
        # Use polygrid2d: ~5x quicker, may avoid fp error accumulation,
        # gives same result to within < 1ppm.
        from numpy.polynomial.polynomial import polygrid2d

        p1 = np.ones(nmatch)
        px = pmatchl[:, 0]
        py = pmatchl[:, 1]
        rmatp = np.c_[
            p1,
            py,
            py * py,
            py * py * py,
            px,
            px * py,
            px * py * py,
            px * px,
            px * px * py,
            px * px * px,
        ]
        [retval, pcoeffs_raw] = cv2.solve(rmatp, pmatchr, flags=cv2.DECOMP_SVD)
        # Put raw coeffs into matrix such that element [i,j] holds Cij in
        # poly = sum (Cij * x^i * y^j).
        pcoeffs = np.zeros((4, 4, 2))
        pcoeffs[
            (0, 0, 0, 0, 1, 1, 1, 2, 2, 3), (0, 1, 2, 3, 0, 1, 2, 0, 1, 0), :
        ] = pcoeffs_raw
        xs = np.arange(self.width)
        ys = np.arange(self.height)
        deformation = polygrid2d(xs, ys, pcoeffs).T.astype(np.float32)

        # Convential memory deformation map
        self.defXcpu = deformation[..., 0].copy()
        self.defYcpu = deformation[..., 1].copy()

        # GPU memory deformation map
        self.defX = cv2.UMat(self.defXcpu)
        self.defY = cv2.UMat(self.defYcpu)

    def get_deforms(self) -> typing.Tuple[np.ndarray, np.ndarray]:
        """Get the deformation maps obtained by the calibration step."""
        return (self.defXcpu, self.defYcpu)

    def process(
        self, img: np.ndarray, sub_factor: typing.Optional[float] = 1.0
    ):
        """Process image data.

        Takes 1 combined numpy (Mat) array and converts to UMat on the fly
        from numpy subimages OPENCV transparent interface will use OPENCL for
        processing.
        Approx 9.2 ms processing time on macbook pro (i7 + Intel Iris Pro)
        """
        result = cv2.subtract(
            cv2.UMat(img[:, 0 : self.width]),
            cv2.remap(
                cv2.multiply(cv2.UMat(img[:, self.width :]), sub_factor),
                self.defX,
                self.defY,
                cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=0,
            ),
        )
        return result

    def process_gpu1(
        self,
        img_l: cv2.UMat,
        img_r: cv2.UMat,
        sub_factor: typing.Optional[float] = 1.0,
    ):
        """Process image data.

        Takes 2 UMat images as arguments,
        OPENCV transparent interface will use OPENCL for processing
        Approx 2.8 ms processing time on macbook pro (i7 + Intel Iris Pro),
        but your images need to be separate UMats already
        """
        # result = cv2.subtract(
        #     img_l,
        #     cv2.remap(
        #         cv2.multiply(img_r, sub_factor),
        #         self.defX,
        #         self.defY,
        #         cv2.INTER_LINEAR,
        #         borderMode=cv2.BORDER_CONSTANT,
        #         borderValue=0,
        #     ),
        # )
        result = cv2.scaleAdd(
            cv2.remap(
                img_r,
                self.defX,
                self.defY,
                cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=0,
            ),
            -sub_factor,
            img_l,
        )
        return result

    def process_gpu2(
        self, img: np.ndarray, sub_factor: typing.Optional[float] = 1.0
    ):
        """Process image data.

        Takes 1 combined numpy (Mat) array and converts to UMat on the fly
        Converts combined image to UMat on gpu then transparent interface
        produces 2 sub image UMats in OPENCL
        OPENCV transparent interface will use OPENCL for processing
        Approx 3.2 ms processing time on macbook pro (i7 + Intel Iris Pro)
        """
        uimg = cv2.UMat(img)
        img_l = cv2.UMat(uimg, (0, self.height), (0, self.width))
        img_r = cv2.UMat(uimg, (0, self.height), (self.width, 2 * self.width))
        result = cv2.subtract(
            img_l,
            cv2.remap(
                cv2.multiply(img_r, sub_factor),
                self.defX,
                self.defY,
                cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=0,
            ),
        )
        return result

    def process_gpu3(
        self, img: np.ndarray, sub_factor: typing.Optional[float] = 1.0
    ):
        """Process image data.

        Takes 1 combined numpy (Mat) array and converts to UMat on the fly
        Converts combined image to UMat on gpu then transparent interface
        produces 2 sub image UMats in OPENCL
        OPENCV transparent interface will use OPENCL for processing, uses
        scaleAdd routine for subtraction step
        Approx 2.7 ms processing time on macbook pro (i7 + Intel Iris Pro)
        """
        uimg = cv2.UMat(img)
        img_l = cv2.UMat(uimg, (0, self.height), (0, self.width))
        img_r = cv2.UMat(uimg, (0, self.height), (self.width, 2 * self.width))
        result = cv2.scaleAdd(
            cv2.remap(
                img_r,
                self.defX,
                self.defY,
                cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=0,
            ),
            -sub_factor,
            img_l,
        )
        return result

    def process_cpu(
        self, img: np.ndarray, sub_factor: typing.Optional[float] = 1.0
    ):
        """Process image data.

        Takes 1 combined numpy (Mat) array and converts to UMat on the fly
        from numpy subimages
        OPENCV transparent interface will use OPENCL for processing
        Approx 7.2 ms processing time on macbook pro (i7 + Intel Iris Pro)
        """
        result = cv2.subtract(
            img[:, 0 : self.width],
            cv2.remap(
                cv2.multiply(img[:, self.width :], sub_factor),
                self.defXcpu,
                self.defYcpu,
                cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=0,
            ),
        )
        return result

    def process_cpu1(
        self, img: np.ndarray, sub_factor: typing.Optional[float] = 1.0
    ):
        """Process image data.

        Takes 1 combined numpy (Mat) array and converts to UMat on the fly
        from numpy subimages
        OPENCV transparent interface will use OPENCL for processing
        Approx 7.2 ms processing time on macbook pro (i7 + Intel Iris Pro)
        """
        result = cv2.scaleAdd(
            cv2.remap(
                img[:, self.width :],
                self.defXcpu,
                self.defYcpu,
                cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=0,
            ),
            -sub_factor,
            img[:, 0 : self.width],
        )
        return result

export interface Review {
  id: string;
  patientName: string;
  rating: number;
  date: string;
  treatment: string;
  cost: number;
  insuranceCovered: number;
  comment: string;
  verified: boolean;
}

export interface Doctor {
  id: string;
  name: string;
  specialty: string;
  experience: number;
  qualifications: string[];
  rating: number;
  reviewCount: number;
  imageUrl: string;
  reviews: Review[];
  aiSummary: string;
}

export interface Hospital {
  id: string;
  name: string;
  location: string;
  rating: number;
  reviewCount: number;
  imageUrl: string;
  description: string;
  specialties: string[];
  acceptedInsurance: string[];
  doctors: Doctor[];
  reviews: Review[];
  aiRecommendation: string;
  avgCostRange: {
    min: number;
    max: number;
  };
  // Additional fields from Lambda response
  trustScore?: number;
  verificationBadge?: string;
  claimApprovalRate?: number;
  insuranceCoveragePercent?: number;
  topDoctorIds?: string[];  // Doctor IDs for lazy loading
  doctorAIReviews?: Record<string, string>;  // Map of doctorId -> AI review
}

export const mockHospitals: Hospital[] = [
  {
    id: "1",
    name: "City General Hospital",
    location: "Downtown, Metro City",
    rating: 4.5,
    reviewCount: 1247,
    imageUrl: "https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?w=400",
    description: "Leading multi-specialty hospital with state-of-the-art facilities and affordable care options.",
    specialties: ["Cardiology", "Orthopedics", "Neurology", "Oncology"],
    acceptedInsurance: ["Blue Cross", "United Health", "Aetna", "Medicare"],
    avgCostRange: { min: 5000, max: 50000 },
    aiRecommendation: "**Excellent choice for cardiac procedures** - This hospital has a proven track record with cardiac surgeries at competitive prices. Based on 342 verified reviews, patients report **average out-of-pocket costs of $3,200** after insurance for coronary procedures. Their cardiology department is highly rated (4.7/5) with experienced surgeons. **Insurance acceptance rate: 94%** for major providers.",
    doctors: [
      {
        id: "d1",
        name: "Dr. Sarah Johnson",
        specialty: "Cardiology",
        experience: 15,
        qualifications: ["MD", "FACC", "Board Certified"],
        rating: 4.8,
        reviewCount: 342,
        imageUrl: "https://images.unsplash.com/photo-1559839734-2b71ea197ec2?w=200",
        aiSummary: "**Top-rated cardiologist** with 15 years of experience. Patients praise her thorough explanations and successful outcomes. **Average surgery cost: $12,000** with 89% insurance coverage. Known for minimally invasive procedures that reduce recovery time by 40%.",
        reviews: [
          {
            id: "r1",
            patientName: "John M.",
            rating: 5,
            date: "2026-02-15",
            treatment: "Coronary Angioplasty",
            cost: 15000,
            insuranceCovered: 13500,
            comment: "Dr. Johnson was exceptional. She explained everything clearly and the procedure was successful. Insurance covered 90%.",
            verified: true,
          },
        ],
      },
      {
        id: "d2",
        name: "Dr. Michael Chen",
        specialty: "Cardiology",
        experience: 12,
        qualifications: ["MD", "PhD", "FACC"],
        rating: 4.7,
        reviewCount: 298,
        imageUrl: "https://images.unsplash.com/photo-1612349317150-e413f6a5b16d?w=200",
        aiSummary: "**Specialist in complex cardiac cases** with excellent patient outcomes. Reviews highlight his expertise in high-risk surgeries. **Cost transparency: 95%** of patients received accurate cost estimates. Average wait time: 2 weeks for consultation.",
        reviews: [],
      },
    ],
    reviews: [
      {
        id: "hr1",
        patientName: "Maria G.",
        rating: 5,
        date: "2026-02-20",
        treatment: "Heart Valve Replacement",
        cost: 45000,
        insuranceCovered: 40000,
        comment: "Excellent facility and staff. The surgery was successful and they worked with my insurance company to minimize my costs.",
        verified: true,
      },
      {
        id: "hr2",
        patientName: "Robert K.",
        rating: 4,
        date: "2026-02-10",
        treatment: "Cardiac Catheterization",
        cost: 8500,
        insuranceCovered: 7500,
        comment: "Professional staff, clean facilities. The billing department was very helpful in explaining costs upfront.",
        verified: true,
      },
    ],
  },
  {
    id: "2",
    name: "St. Mary's Medical Center",
    location: "Westside, Metro City",
    rating: 4.3,
    reviewCount: 892,
    imageUrl: "https://images.unsplash.com/photo-1586773860418-d37222d8fce3?w=400",
    description: "Compassionate care with focus on affordable treatment options and flexible payment plans.",
    specialties: ["Oncology", "Pediatrics", "Maternity", "General Surgery"],
    acceptedInsurance: ["Medicaid", "Blue Cross", "Cigna", "Humana"],
    avgCostRange: { min: 3000, max: 40000 },
    aiRecommendation: "**Best value for oncology treatments** - Specialized in cancer care with comprehensive support programs. Verified patient data shows **average chemotherapy costs of $4,800 per cycle** with financial assistance programs reducing out-of-pocket by up to 60%. **Medicaid acceptance: 100%**. Treatment timelines are well-documented with 87% of patients reporting accurate time estimates.",
    doctors: [
      {
        id: "d3",
        name: "Dr. Emily Rodriguez",
        specialty: "Oncology",
        experience: 18,
        qualifications: ["MD", "FASCO", "Clinical Oncology"],
        rating: 4.9,
        reviewCount: 456,
        imageUrl: "https://images.unsplash.com/photo-1594824476967-48c8b964273f?w=200",
        aiSummary: "**Leading oncologist** with exceptional patient satisfaction. Known for personalized treatment plans and compassionate care. **Financial counseling: 100%** of patients receive detailed cost breakdowns before treatment. Insurance claim success rate: 96%.",
        reviews: [],
      },
    ],
    reviews: [
      {
        id: "hr3",
        patientName: "Linda S.",
        rating: 5,
        date: "2026-02-18",
        treatment: "Chemotherapy (6 cycles)",
        cost: 28000,
        insuranceCovered: 25000,
        comment: "The financial counseling team helped me navigate insurance and payment options. They even connected me with assistance programs.",
        verified: true,
      },
    ],
  },
  {
    id: "3",
    name: "Metropolitan Orthopedic Institute",
    location: "North District, Metro City",
    rating: 4.6,
    reviewCount: 1563,
    imageUrl: "https://images.unsplash.com/photo-1538108149393-fbbd81895907?w=400",
    description: "Specialized orthopedic care with transparent pricing and excellent insurance coordination.",
    specialties: ["Orthopedics", "Sports Medicine", "Physical Therapy", "Joint Replacement"],
    acceptedInsurance: ["Blue Cross", "United Health", "Aetna", "Medicare", "Workers Comp"],
    avgCostRange: { min: 8000, max: 60000 },
    aiRecommendation: "**Premier choice for joint replacements** - Industry-leading outcomes for knee and hip surgeries. Patient reviews show **average total knee replacement cost: $18,500** with insurance covering 75-85%. Recovery programs included in pricing. **Wait time: 3-4 weeks** for surgery scheduling. Post-op physical therapy bundled into treatment costs.",
    doctors: [
      {
        id: "d4",
        name: "Dr. James Anderson",
        specialty: "Orthopedic Surgery",
        experience: 20,
        qualifications: ["MD", "FAAOS", "Joint Replacement Specialist"],
        rating: 4.8,
        reviewCount: 687,
        imageUrl: "https://images.unsplash.com/photo-1622253692010-333f2da6031d?w=200",
        aiSummary: "**Expert in minimally invasive joint replacement** with over 2,000 successful surgeries. Patients report **40% faster recovery** compared to traditional methods. Transparent pricing with detailed cost estimates provided during consultation. Average patient satisfaction: 96%.",
        reviews: [],
      },
      {
        id: "d5",
        name: "Dr. Patricia Williams",
        specialty: "Sports Medicine",
        experience: 14,
        qualifications: ["MD", "FAAOS", "Sports Medicine"],
        rating: 4.7,
        reviewCount: 423,
        imageUrl: "https://images.unsplash.com/photo-1643297654416-05795d62e39c?w=200",
        aiSummary: "**Specialist in athletic injuries** serving both professional and amateur athletes. Known for conservative treatment approaches that avoid unnecessary surgery. **Cost-effective**: 68% of patients avoid surgery through physical therapy and innovative treatments.",
        reviews: [],
      },
    ],
    reviews: [
      {
        id: "hr4",
        patientName: "David T.",
        rating: 5,
        date: "2026-02-12",
        treatment: "Total Knee Replacement",
        cost: 22000,
        insuranceCovered: 18000,
        comment: "Dr. Anderson was fantastic. Got detailed cost breakdown before surgery. Insurance covered most of it. Back to walking in 6 weeks!",
        verified: true,
      },
    ],
  },
];

export function searchHospitals(query: string): Hospital[] {
  if (!query.trim()) {
    return [];
  }

  const lowerQuery = query.toLowerCase();
  
  // Simple search algorithm - in production this would be more sophisticated
  return mockHospitals.filter((hospital) => {
    return (
      hospital.name.toLowerCase().includes(lowerQuery) ||
      hospital.description.toLowerCase().includes(lowerQuery) ||
      hospital.specialties.some((s) => s.toLowerCase().includes(lowerQuery)) ||
      hospital.location.toLowerCase().includes(lowerQuery) ||
      hospital.aiRecommendation.toLowerCase().includes(lowerQuery)
    );
  });
}

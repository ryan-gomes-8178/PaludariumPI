-- Add out_of_range column to SensorHistory to track measurements that are outside valid range
ALTER TABLE "SensorHistory" ADD COLUMN "out_of_range" BOOLEAN NOT NULL DEFAULT 0;

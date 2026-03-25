import { LucideIcon } from 'lucide-react';
import clsx from 'clsx';

interface StatCardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  trend?: {
    value: number;
    label: string;
  };
  color?: 'green' | 'blue' | 'purple' | 'orange';
}

function StatCard({ title, value, icon: Icon, trend, color = 'green' }: StatCardProps) {
  const colorClasses = {
    green: 'from-climate-green-500 to-climate-green-600',
    blue: 'from-climate-blue-500 to-climate-blue-600',
    purple: 'from-purple-500 to-purple-600',
    orange: 'from-orange-500 to-orange-600'
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <p className="text-sm font-medium text-gray-600 mb-1">{title}</p>
          <p className="text-3xl font-bold text-gray-900">{value}</p>
          
          {trend && (
            <p className={clsx(
              'text-sm mt-2',
              trend.value >= 0 ? 'text-green-600' : 'text-red-600'
            )}>
              <span className="font-medium">
                {trend.value >= 0 ? '+' : ''}{trend.value}%
              </span>{' '}
              <span className="text-gray-500">{trend.label}</span>
            </p>
          )}
        </div>
        
        <div className={clsx(
          'p-4 rounded-xl bg-gradient-to-br',
          colorClasses[color]
        )}>
          <Icon className="h-8 w-8 text-white" />
        </div>
      </div>
    </div>
  );
}

export default StatCard;

